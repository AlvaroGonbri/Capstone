import json
import uuid
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase, override_settings
from requests.structures import CaseInsensitiveDict

from accesos.models import EventoAcceso, PersonaAutorizada, PuntoAcceso
from alertas.models import Alerta, HostProblemaZabbix
from infraestructura.zabbix_client import ZabbixError
from intervenciones.models import Intervencion
from inventario.models import Activo
from mediciones.models import Medicion, Sensor, Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol

from . import gemini, resumen
from .agregacion import Periodo, construir_reporte


CHILE = ZoneInfo('America/Santiago')
URL = '/api/reportes/resumen/'
OCTUBRE = {'desde': '2026-10-01', 'hasta': '2026-10-31'}


def cuando(dia, hora=12, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=CHILE)


def hora_zabbix(dia, hora, promedio, minimo=None, maximo=None):
    return {'clock': int(cuando(dia, hora).timestamp()), 'avg': promedio,
            'min': promedio if minimo is None else minimo, 'max': promedio if maximo is None else maximo}


# zabbix[host,agent,available] en Zabbix 7: 0 = no disponible, 1 = disponible, 2 = desconocido.
ZABBIX = [
    # mysql01: una hora disponible y otra a medias -> 75 %.
    {'host': 'mysql01', 'horas': [hora_zabbix(10, 9, 1.0), hora_zabbix(10, 10, 0.5, 0, 1)]},
    # SERVER: solo "desconocido" -> no cuenta.
    {'host': 'SERVER', 'horas': [hora_zabbix(10, 9, 2.0)]},
]


class ReportesTestCase(TablasNoGestionadasTestCase):
    modelos = TablasNoGestionadasTestCase.modelos + (
        Activo, HostProblemaZabbix, Alerta, Intervencion, PersonaAutorizada, PuntoAcceso, EventoAcceso,
    )

    def setUp(self):
        cache.clear()
        self.sala = Ubicacion.objects.create(sala='Sala principal')
        self.rack = Ubicacion.objects.create(sala='Sala principal', zona='Zona A', rack='R1', ubicacion_padre=self.sala)
        self.otra = Ubicacion.objects.create(sala='Sala de respaldo')
        self.s1 = self.sensor('arduino-01', self.rack)
        self.s2 = self.sensor('arduino-02', self.otra)

        # Ambiente: 2 lecturas reales en la sala, 1 simulada (no cuenta) y 1 real en la otra sala.
        self.medicion(self.s1, 20, 40, 'Real')
        self.medicion(self.s1, 24, 50, 'Real')
        self.medicion(self.s1, 99, 99, 'Simulado')
        self.medicion(self.s2, 30, 60, 'Real')

        # Alertas ambientales: una cerrada en 30 min, otra sin fecha de cierre y otra fuera del período.
        Alerta.objects.create(origen='IoT', condicion='Temperatura fuera de rango', severidad='Critica',
                              estado='Cerrada', fecha_apertura=cuando(5, 10), fecha_cierre=cuando(5, 10, 30), sensor=self.s1)
        Alerta.objects.create(origen='IoT', condicion='Humedad fuera de rango', severidad='Advertencia',
                              estado='Cerrada', fecha_apertura=cuando(6), sensor=self.s2)
        Alerta.objects.create(origen='IoT', condicion='Humedad fuera de rango', severidad='Advertencia',
                              estado='Cerrada', fecha_apertura=datetime(2026, 9, 30, 12, tzinfo=CHILE), sensor=self.s1)

        # Zabbix: un problema alto en un servidor inventariado en el rack (sigue abierto) y otro de un host sin inventariar.
        activo = Activo.objects.create(codigo='mysql01', nombre='Nodo 01', numero_serie='SN1', ubicacion=self.rack,
                                       fecha_alta=cuando(1))
        problema = HostProblemaZabbix.objects.create(identificador_externo='e1', activo_id=activo.id, estado='PROBLEM')
        Alerta.objects.create(origen='Zabbix', condicion='mysql01: Disco casi lleno', severidad='Alta', estado='Nueva',
                              fecha_apertura=cuando(7), host_problema_zabbix=problema)
        Alerta.objects.create(origen='Zabbix', condicion='router01: Latencia alta', severidad='Advertencia',
                              estado='Cerrada', fecha_apertura=cuando(8), fecha_cierre=cuando(8, 13))

        # Intervenciones: una ejecutada y una aprobada en octubre; una de noviembre que no cuenta.
        Intervencion.objects.create(objetivo='Cambio de disco', rack='RACK-PROD-01', estado='Ejecutada',
                                    fecha_solicitud=cuando(3), fecha_cierre=cuando(4))
        Intervencion.objects.create(objetivo='Revisión', estado='Aprobada', fecha_solicitud=cuando(20))
        Intervencion.objects.create(objetivo='Otra', estado='Pendiente', fecha_solicitud=datetime(2026, 11, 2, tzinfo=CHILE))

        # Accesos: en el rack 2 permitidos, 1 denegado y 3 fallas del lector; en la otra sala 1 denegado.
        puerta = PuntoAcceso.objects.create(nombre='Puerta', ubicacion=self.rack, estado='Activo')
        otra_puerta = PuntoAcceso.objects.create(nombre='Puerta 2', ubicacion=self.otra, estado='Activo')
        for resultado, n, punto in (('Permitido', 2, puerta), ('Denegado', 1, puerta), ('Error', 3, puerta),
                                    ('Denegado', 1, otra_puerta)):
            for _ in range(n):
                EventoAcceso.objects.create(identificador_biometrico_externo='EXT-1', punto_acceso=punto,
                                            fecha_hora=cuando(12), resultado=resultado)

        self.admin = cliente_con_rol('admin', 'Administrador')

    def sensor(self, codigo, ubicacion):
        return Sensor.objects.create(codigo=codigo, tipo='ESP32', ubicacion=ubicacion, estado='Activo',
                                     intervalo_esperado_segundos=60, device_key_hash='x')

    def medicion(self, sensor, temperatura, humedad, origen):
        Medicion.objects.create(sensor=sensor, evento_id=str(uuid.uuid4()), temperatura=temperatura, humedad=humedad,
                                fecha_hora_medicion=cuando(10), fecha_hora_recepcion=cuando(10), origen=origen)


@override_settings(GEMINI_API_KEY='')
@mock.patch('reportes.agregacion.ZabbixClient')
class ResumenDelPeriodoTests(ReportesTestCase):
    def test_cuenta_todo_el_periodo_con_los_datos_de_cada_modulo(self, zabbix):
        zabbix.return_value.disponibilidad_agentes.return_value = ZABBIX

        datos = self.admin.get(URL, OCTUBRE).json()

        self.assertEqual(datos['ambiente']['lecturas'], 3)  # la simulada no cuenta (RN-06)
        self.assertEqual(datos['ambiente']['temperatura']['maximo'], 30.0)
        a = datos['alertas_ambientales']
        self.assertEqual((a['total'], a['resolucion_promedio_min'], a['resolucion_con_datos']), (2, 30.0, 1))
        z = datos['problemas_zabbix']
        self.assertEqual((z['total'], z['altos_o_criticos'], z['abiertos_al_cierre']), (2, 1, 1))
        i = datos['intervenciones']
        self.assertEqual((i['total'], i['cerradas'], i['abiertas']), (2, 1, 1))
        self.assertEqual(datos['accesos'], {'permitidos': 2, 'denegados': 2, 'fallas_del_lector': 3})
        self.assertEqual(datos['disponibilidad']['porcentaje'], 75.0)
        self.assertEqual({h['host']: h['porcentaje'] for h in datos['disponibilidad']['hosts']},
                         {'mysql01': 75.0, 'SERVER': None})
        self.assertEqual(len(datos['disponibilidad']['por_dia']), 31)
        self.assertEqual(datos['eventos'][0]['etiqueta'], 'Crítica')  # lo más grave primero
        self.assertEqual(datos['resumen']['origen'], 'plantilla')
        self.assertIn('75 %', datos['resumen']['texto'])

    def test_la_zona_incluye_lo_que_cuelga_de_ella(self, zabbix):
        zabbix.return_value.disponibilidad_agentes.return_value = ZABBIX

        datos = self.admin.get(URL, {**OCTUBRE, 'zona': self.sala.id}).json()

        self.assertEqual(datos['periodo']['zona']['nombre'], 'Sala principal')
        self.assertEqual(datos['ambiente']['lecturas'], 2)
        self.assertEqual(datos['alertas_ambientales']['total'], 1)
        self.assertEqual(datos['problemas_zabbix']['total'], 1)  # solo el servidor inventariado en el rack
        self.assertEqual(datos['accesos'], {'permitidos': 2, 'denegados': 1, 'fallas_del_lector': 3})
        self.assertEqual([h['host'] for h in datos['disponibilidad']['hosts']], ['mysql01'])
        self.assertEqual(datos['intervenciones']['total'], 2)  # sin filtro de zona (rack en texto libre)

    def test_si_zabbix_no_responde_el_reporte_igual_se_entrega(self, zabbix):
        zabbix.return_value.disponibilidad_agentes.side_effect = ZabbixError('sin conexión')

        respuesta = self.admin.get(URL, OCTUBRE)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.json()['disponibilidad']['porcentaje'])
        self.assertIn('Zabbix no respondió', respuesta.json()['disponibilidad']['error'])
        self.assertIn('no hay datos de disponibilidad', respuesta.json()['resumen']['texto'])

    def test_periodos_invalidos(self, zabbix):
        self.assertEqual(self.admin.get(URL, {'desde': '2026-10-10', 'hasta': '2026-10-01'}).status_code, 400)
        self.assertEqual(self.admin.get(URL, {'desde': '2026-01-01', 'hasta': '2026-10-31'}).status_code, 400)

    def test_lo_consultan_todos_menos_contratistas(self, zabbix):
        zabbix.return_value.disponibilidad_agentes.return_value = []
        self.assertEqual(cliente_con_rol('tecnico', 'Tecnico').get(URL, OCTUBRE).status_code, 200)
        self.assertEqual(cliente_con_rol('auditor', 'Auditor').get(URL, OCTUBRE).status_code, 200)
        self.assertEqual(cliente_con_rol('contratista', 'Contratistas').get(URL, OCTUBRE).status_code, 403)

    def test_pdf(self, zabbix):
        zabbix.return_value.disponibilidad_agentes.return_value = ZABBIX

        respuesta = self.admin.get('/api/reportes/pdf/', OCTUBRE)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertTrue(respuesta.content.startswith(b'%PDF'))
        self.assertIn('SICMA-reporte-2026-10-01_2026-10-31.pdf', respuesta['Content-Disposition'])


@override_settings(GEMINI_API_KEY='clave-de-prueba')
class ResumenConIATests(ReportesTestCase):
    def reporte(self):
        with mock.patch('reportes.agregacion.ZabbixClient') as zabbix:
            zabbix.return_value.disponibilidad_agentes.return_value = ZABBIX
            from datetime import date
            return construir_reporte(Periodo(date(2026, 10, 1), date(2026, 10, 31), self.sala))

    @mock.patch('reportes.gemini.generar')
    def test_usa_el_texto_de_gemini_y_no_le_envia_nombres(self, generar):
        generar.return_value = ('Entre el 1 y el 31 de octubre de 2026 la disponibilidad fue 75 %. '
                                'Hubo 1 alerta ambiental y 2 accesos permitidos.')

        r = resumen.resumen(self.reporte())

        self.assertEqual((r['origen'], r['modelo']), ('ia', gemini.modelo()))
        enviado = generar.call_args.args[0]
        for nombre in ('Sala principal', 'mysql01', 'arduino', 'RACK-PROD-01', 'Disco casi lleno', 'admin'):
            self.assertNotIn(nombre, enviado)
        self.assertTrue(json.loads(enviado)['periodo']['filtrado_por_zona'])

    @mock.patch('reportes.gemini.generar')
    def test_si_inventa_una_cifra_se_usa_la_plantilla(self, generar):
        generar.return_value = 'La disponibilidad fue 99,9 % y hubo 1 alerta ambiental.'

        r = resumen.resumen(self.reporte())

        self.assertEqual(r['origen'], 'plantilla')
        self.assertIn('cifras que no están en los datos', r['motivo'])

    @mock.patch('reportes.gemini.generar', side_effect=gemini.GeminiNoDisponible('Se alcanzó el límite del nivel gratuito de Gemini.'))
    def test_si_gemini_falla_se_usa_la_plantilla_y_no_se_reintenta_enseguida(self, generar):
        reporte = self.reporte()

        primero = resumen.resumen(reporte)
        segundo = resumen.resumen(reporte)

        self.assertEqual((primero['origen'], segundo['origen']), ('plantilla', 'plantilla'))
        self.assertIn('límite', segundo['motivo'])
        self.assertEqual(generar.call_count, 1)

    @override_settings(GEMINI_API_KEY='')
    def test_sin_clave_no_se_llama_a_gemini(self):
        with mock.patch('reportes.gemini.generar') as generar:
            r = resumen.resumen(self.reporte())
        generar.assert_not_called()
        self.assertIn('falta GEMINI_API_KEY', r['motivo'])

    def test_verificacion_de_cifras(self):
        datos = {'a': 99.25, 'b': 1086, 'c': '2026-10-01'}
        self.assertEqual(resumen.cifras_ajenas('Fue 99,3 % (99,25) con 1086 y 1.086 fallas el 1 de 10 de 2026.', datos), [])
        self.assertEqual(resumen.cifras_ajenas('Fue 98 %.', datos), ['98'])


class ClienteGeminiTests(TestCase):
    @override_settings(GEMINI_API_KEY='clave-secreta', GEMINI_MODELO='gemini-3.5-flash')
    @mock.patch('reportes.gemini.requests.post')
    def test_la_clave_va_en_la_cabecera_y_el_cupo_agotado_se_informa(self, post):
        post.return_value = mock.Mock(status_code=200, headers=CaseInsensitiveDict())
        post.return_value.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'funciona'}]}}]}

        self.assertEqual(gemini.generar('hola'), 'funciona')
        llamada = post.call_args
        self.assertNotIn('clave-secreta', llamada.args[0])
        self.assertEqual(llamada.kwargs['headers']['x-goog-api-key'], 'clave-secreta')

        post.return_value = mock.Mock(status_code=429)
        with self.assertRaisesMessage(gemini.GeminiNoDisponible, 'límite'):
            gemini.generar('hola')

    @override_settings(GEMINI_API_KEY='clave-secreta', GEMINI_MODELO='gemini-1.0-retirado')
    @mock.patch('reportes.gemini.requests.post')
    def test_modelo_retirado_o_saturado_dice_que_hacer(self, post):
        post.return_value = mock.Mock(status_code=404)
        with self.assertRaisesMessage(gemini.GeminiNoDisponible, 'ya no ofrece el modelo gemini-1.0-retirado'):
            gemini.generar('hola')

        post.return_value = mock.Mock(status_code=503)
        with self.assertRaisesMessage(gemini.GeminiNoDisponible, 'saturado'):
            gemini.generar('hola')

    @override_settings(GEMINI_API_KEY='clave-secreta', GEMINI_MODELO='gemini-9-flash')
    @mock.patch('reportes.gemini.requests.post')
    def test_si_el_modelo_no_acepta_el_razonamiento_minimo_reintenta_con_bajo(self, post):
        rechazo = mock.Mock(status_code=400)
        rechazo.json.return_value = {'error': {'message': 'Thinking level MINIMAL is not supported for this model.'}}
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {'candidates': [{'content': {'parts': [
            {'text': 'pensando...', 'thought': True}, {'text': 'funciona'}]}}]}
        post.side_effect = [rechazo, ok]

        self.assertEqual(gemini.generar('hola', max_tokens=16), 'funciona')
        primera, segunda = (c.kwargs['json']['generationConfig'] for c in post.call_args_list)
        self.assertEqual(primera['thinkingConfig'], {'thinkingLevel': 'minimal'})
        self.assertEqual(segunda['thinkingConfig'], {'thinkingLevel': 'low'})
        self.assertGreater(segunda['maxOutputTokens'], 16)

    def test_razonamiento_segun_la_generacion(self):
        self.assertEqual(gemini._razonamiento('gemini-2.5-flash'), {'thinkingBudget': 0})
        self.assertIsNone(gemini._razonamiento('gemini-2.5-pro'))
        self.assertEqual(gemini._razonamiento('gemini-3.5-flash'), {'thinkingLevel': 'minimal'})


class FraccionDisponibleTests(TestCase):
    """zabbix[host,agent,available] en Zabbix 7: 0 = no disponible, 1 = disponible, 2 = desconocido."""

    def fraccion(self, promedio, minimo, maximo):
        from .agregacion import _fraccion_disponible
        return _fraccion_disponible({'clock': 0, 'avg': promedio, 'min': minimo, 'max': maximo})

    def test_hora_apagado_completa_es_cero(self):
        # Caso real (mysql02, 19-11-2026): servidor apagado -> min = avg = max = 0. Antes se descartaba.
        self.assertEqual(self.fraccion(0.0, 0.0, 0.0), 0.0)

    def test_hora_disponible_completa(self):
        self.assertEqual(self.fraccion(1.0, 1.0, 1.0), 1.0)

    def test_hora_en_que_se_apago(self):
        self.assertAlmostEqual(self.fraccion(0.25, 0.0, 1.0), 0.25)

    def test_solo_desconocido_no_cuenta(self):
        self.assertIsNone(self.fraccion(2.0, 2.0, 2.0))

    def test_disponible_y_desconocido_cuenta_como_disponible(self):
        self.assertEqual(self.fraccion(1.5, 1.0, 2.0), 1.0)

    def test_no_disponible_y_desconocido_cuenta_como_caida(self):
        self.assertEqual(self.fraccion(1.0, 0.0, 2.0), 0.0)
