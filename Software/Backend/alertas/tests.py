import uuid
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from inventario.models import Activo
from mediciones.models import Sensor, Ubicacion, UmbralAmbiental
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol

from .models import Alerta, HostProblemaZabbix, Notificacion, ReglaAlerta


CLAVE_DISPOSITIVO = 'clave-del-esp32'


@override_settings(ALERTAS_CORREO_ASINCRONO=False, DEFAULT_FROM_EMAIL='sicma@sicma.test')
class AlertasAmbientalesTests(TablasNoGestionadasTestCase):
    modelos = TablasNoGestionadasTestCase.modelos + (Activo, HostProblemaZabbix, Alerta, Notificacion, ReglaAlerta)

    def setUp(self):
        self.zona = Ubicacion.objects.create(sala='Sala principal', zona='Zona A')
        self.sensor = Sensor.objects.create(
            codigo='arduino-01', tipo='DHT22', ubicacion=self.zona, estado='Activo',
            intervalo_esperado_segundos=60, device_key_hash=make_password(CLAVE_DISPOSITIVO),
        )
        for variable, minimo, maximo in (('Temperatura', 18, 27), ('Humedad', 35, 60)):
            UmbralAmbiental.objects.create(
                ubicacion=self.zona, variable=variable, valor_minimo=minimo,
                valor_maximo=maximo, version=1, vigente_desde=timezone.now(),
            )
        ReglaAlerta.objects.create(
            fuente='IoT', condicion=ReglaAlerta.condicion_zona(self.zona.id),
            severidad='Critica', destinatarios=['responsable@sicma.test'],
        )
        self.dispositivo = APIClient()

    def enviar(self, temperatura, humedad, evento_id=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.dispositivo.post('/api/mediciones/', {
                'sensor_codigo': 'arduino-01',
                'evento_id': str(evento_id or uuid.uuid4()),
                'temperatura': temperatura,
                'humedad': humedad,
                'fecha_hora_medicion': timezone.now().isoformat(),
            }, format='json', HTTP_X_DEVICE_KEY=CLAVE_DISPOSITIVO)

    def test_lectura_en_rango_no_genera_alerta(self):
        self.assertEqual(self.enviar(22, 50).status_code, 201)
        self.assertEqual(Alerta.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_lectura_fuera_de_rango_abre_alerta_y_avisa_por_correo(self):
        self.assertEqual(self.enviar(22, 68).status_code, 201)

        alerta = Alerta.objects.get()
        self.assertEqual((alerta.origen, alerta.severidad, alerta.estado), ('IoT', 'Critica', 'Nueva'))
        self.assertTrue(alerta.condicion.startswith('Humedad fuera de rango'))
        self.assertIn('68', alerta.condicion)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['responsable@sicma.test'])
        self.assertIn('Humedad fuera de rango', mail.outbox[0].subject)
        notificacion = Notificacion.objects.get()
        self.assertEqual((notificacion.alerta_id, notificacion.canal, notificacion.resultado), (alerta.id, 'SMTP', 'Enviado'))

    def test_repeticiones_suman_a_la_misma_alerta_sin_nuevos_correos(self):
        self.enviar(22, 68)
        self.enviar(22, 70)
        self.enviar(22, 72)

        alerta = Alerta.objects.get()
        self.assertEqual(alerta.contador_ocurrencias, 3)
        self.assertIn('72', alerta.condicion)  # la condición muestra la última lectura
        self.assertEqual(len(mail.outbox), 1)

    def test_volver_al_rango_cierra_y_una_nueva_salida_abre_otra_alerta(self):
        self.enviar(22, 68)
        self.enviar(22, 50)
        self.assertEqual(Alerta.objects.get().estado, 'Cerrada')

        self.enviar(22, 68)
        self.assertEqual(list(Alerta.objects.order_by('id').values_list('estado', flat=True)), ['Cerrada', 'Nueva'])
        self.assertEqual(len(mail.outbox), 2)

    def test_cada_variable_tiene_su_propia_alerta(self):
        self.enviar(30, 68)
        self.assertEqual(
            sorted(a.condicion.split(' ')[0] for a in Alerta.objects.all()),
            ['Humedad', 'Temperatura'],
        )

    def test_lectura_duplicada_no_se_evalua_dos_veces(self):
        evento = uuid.uuid4()
        self.enviar(22, 68, evento)
        self.assertEqual(self.enviar(22, 68, evento).status_code, 200)
        self.assertEqual(Alerta.objects.get().contador_ocurrencias, 1)

    def test_zona_sin_umbrales_no_genera_alertas(self):
        UmbralAmbiental.objects.all().delete()
        self.enviar(99, 99)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_zona_sin_responsables_abre_la_alerta_sin_enviar_correo(self):
        ReglaAlerta.objects.all().delete()
        self.enviar(22, 68)
        self.assertEqual(Alerta.objects.count(), 1)
        self.assertEqual((len(mail.outbox), Notificacion.objects.count()), (0, 0))

    def test_falla_del_smtp_queda_registrada_y_no_afecta_la_lectura(self):
        with patch('alertas.servicio.EmailMessage.send', side_effect=OSError('SMTP caído')):
            respuesta = self.enviar(22, 68)
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Notificacion.objects.get().resultado, 'Fallido')

    def test_api_lista_alertas_abiertas_y_administra_responsables(self):
        self.enviar(22, 68)
        tecnico = cliente_con_rol('tec', 'Tecnico')
        abiertas = tecnico.get('/api/alertas/').json()
        self.assertEqual([(a['sensor_codigo'], a['ubicacion']) for a in abiertas], [('arduino-01', self.zona.id)])

        url = f'/api/alertas/responsables/{self.zona.id}/'
        self.assertEqual(tecnico.put(url, {'correos': ['x@sicma.test']}, format='json').status_code, 403)
        admin = cliente_con_rol('admin', 'Administrador')
        self.assertEqual(admin.put(url, {'correos': ['no-es-correo']}, format='json').status_code, 400)
        respuesta = admin.put(url, {'correos': ['A@sicma.test', 'a@sicma.test', 'b@sicma.test']}, format='json')
        self.assertEqual(respuesta.json()['correos'], ['a@sicma.test', 'b@sicma.test'])
        self.assertEqual(
            tecnico.get('/api/alertas/responsables/').json(),
            [{'ubicacion': self.zona.id, 'correos': ['a@sicma.test', 'b@sicma.test']}],
        )


@override_settings(ZABBIX_WEBHOOK_SECRET='secreto-de-prueba')
class EventosZabbixTests(TablasNoGestionadasTestCase):
    """RF-INF-02: los eventos del webhook de Zabbix quedan registrados como alertas."""

    modelos = TablasNoGestionadasTestCase.modelos + (Activo, HostProblemaZabbix, Alerta)
    url = '/api/integraciones/zabbix/webhook/'

    def enviar(self, status='PROBLEM', event_id='51350', severity='High', token='secreto-de-prueba'):
        return APIClient().post(self.url, {
            'event_id': event_id, 'host': 'router01', 'problem': 'MySQL Router caído',
            'severity': severity, 'status': status, 'time': '2026.10.17 09:30:00',
        }, format='json', HTTP_X_ZABBIX_TOKEN=token)

    def test_problem_registra_el_evento_y_abre_una_alerta(self):
        respuesta = self.enviar()

        self.assertEqual(respuesta.status_code, 202)
        problema = HostProblemaZabbix.objects.get()
        self.assertEqual((problema.identificador_externo, problema.estado, problema.severidad), ('51350', 'PROBLEM', 'High'))
        alerta = Alerta.objects.get()
        self.assertEqual((alerta.origen, alerta.severidad, alerta.estado), ('Zabbix', 'Alta', 'Nueva'))
        self.assertEqual(alerta.condicion, 'router01: MySQL Router caído')
        self.assertEqual(alerta.host_problema_zabbix_id, problema.id)
        self.assertEqual(respuesta.json()['alerta_id'], alerta.id)

    def test_resolved_cierra_la_alerta(self):
        self.enviar()
        respuesta = self.enviar(status='RESOLVED')

        self.assertEqual(respuesta.json()['estado_alerta'], 'Cerrada')
        self.assertEqual(HostProblemaZabbix.objects.get().estado, 'RESOLVED')
        self.assertEqual(Alerta.objects.get().estado, 'Cerrada')

    def test_reintentos_de_zabbix_no_duplican(self):
        self.enviar()
        self.enviar()
        self.assertEqual((HostProblemaZabbix.objects.count(), Alerta.objects.count()), (1, 1))
        self.assertEqual(Alerta.objects.get().contador_ocurrencias, 1)

    def test_resolved_de_un_problema_desconocido_se_registra_sin_alerta(self):
        respuesta = self.enviar(status='RESOLVED', event_id='999')
        self.assertEqual(respuesta.status_code, 202)
        self.assertIsNone(respuesta.json()['alerta_id'])
        self.assertEqual(HostProblemaZabbix.objects.get().estado, 'RESOLVED')
        self.assertEqual(Alerta.objects.count(), 0)

    def test_severidades_de_zabbix_se_traducen(self):
        for i, (zabbix, sicma) in enumerate((('Information', 'Informativa'), ('Warning', 'Advertencia'),
                                              ('Average', 'Alta'), ('Disaster', 'Critica'), ('Desastre', 'Critica'))):
            self.enviar(event_id=str(100 + i), severity=zabbix)
            self.assertEqual(Alerta.objects.get(host_problema_zabbix__identificador_externo=str(100 + i)).severidad, sicma)

    def test_cuerpo_invalido_o_token_incorrecto_no_registran_nada(self):
        self.assertEqual(self.enviar(event_id='{EVENT.ID}').status_code, 400)
        self.assertEqual(self.enviar(status='OTRO').status_code, 400)
        self.assertEqual(self.enviar(token='malo').status_code, 403)
        self.assertEqual((HostProblemaZabbix.objects.count(), Alerta.objects.count()), (0, 0))

    def test_alertas_de_zabbix_aparecen_en_la_api(self):
        self.enviar()
        alertas = cliente_con_rol('aud', 'Auditor').get('/api/alertas/', {'origen': 'Zabbix'}).json()
        self.assertEqual([(a['condicion'], a['evento_zabbix']) for a in alertas], [('router01: MySQL Router caído', '51350')])



class GestionDeAlertasTests(TablasNoGestionadasTestCase):
    """El Técnico o el Administrador reconoce y cierra alertas; queda quién y cuándo."""

    modelos = TablasNoGestionadasTestCase.modelos + (HostProblemaZabbix, Alerta)

    def setUp(self):
        self.alerta = Alerta.objects.create(
            origen='Zabbix', condicion='mysql01: caído', severidad='Alta', estado='Nueva', fecha_apertura=timezone.now(),
        )
        self.tecnico = cliente_con_rol('tec', 'Tecnico')

    def test_reconocer_y_cerrar_con_trazabilidad(self):
        url = f'/api/alertas/{self.alerta.id}/'
        reconocida = self.tecnico.post(url + 'reconocer/', {'comentario': 'Revisando el nodo'}, format='json').json()
        self.assertEqual(reconocida['estado'], 'Reconocida')
        self.assertEqual((reconocida['ultima_gestion']['usuario'], reconocida['ultima_gestion']['comentario']), ('tec', 'Revisando el nodo'))
        self.assertEqual(self.tecnico.post(url + 'reconocer/', {}, format='json').status_code, 409)

        cerrada = self.tecnico.post(url + 'cerrar/', {}, format='json').json()
        self.assertEqual((cerrada['estado'], cerrada['ultima_gestion']['accion']), ('Cerrada', 'Cerrada'))
        self.assertEqual(self.tecnico.post(url + 'cerrar/', {}, format='json').status_code, 409)
        self.assertEqual(cliente_con_rol('aud', 'Auditor').get('/api/alertas/').json(), [])  # ya no está abierta

    def test_auditor_y_jefatura_solo_consultan(self):
        for usuario, rol in (('aud', 'Auditor'), ('jefe', 'Jefatura')):
            cliente = cliente_con_rol(usuario, rol)
            self.assertEqual(cliente.post(f'/api/alertas/{self.alerta.id}/cerrar/', {}, format='json').status_code, 403)
            self.assertEqual(cliente.get('/api/alertas/').status_code, 200)
