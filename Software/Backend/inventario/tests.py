from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from alertas.models import Alerta, HostProblemaZabbix, Notificacion
from mediciones.models import Sensor, Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol

from .models import Activo, HistorialActivo, TipoActivo


User = get_user_model()


class InventarioTestCase(TablasNoGestionadasTestCase):
    modelos = TablasNoGestionadasTestCase.modelos + (Activo, HistorialActivo)

    def setUp(self):
        self.sala = Ubicacion.objects.create(sala='Sala principal', zona='Zona A')
        self.admin = cliente_con_rol('admin', 'Administrador')
        self.tecnico = cliente_con_rol('tecnico', 'Tecnico')
        self.auditor = cliente_con_rol('auditor', 'Auditor')
        self.responsable = User.objects.create_user(username='resp', email='resp@sicma.test', password='x', first_name='Ana')

    def alta(self, cliente=None, **extra):
        datos = {
            'codigo': 'mysql01', 'nombre': 'Nodo MySQL 01', 'tipo': 'Servidor', 'marca': 'Dell',
            'numero_serie': 'SN-001', 'ubicacion': self.sala.id, 'criticidad': 'Alta', **extra,
        }
        return (cliente or self.tecnico).post('/api/activos/', datos, format='json')


class ActivosTests(InventarioTestCase):
    def test_tecnico_registra_un_activo_y_queda_el_alta_en_el_historial(self):
        respuesta = self.alta(responsable=self.responsable.id)

        self.assertEqual(respuesta.status_code, 201)
        datos = respuesta.json()
        self.assertEqual((datos['estado'], datos['responsable_nombre'], datos['responsable_email']), ('Operativo', 'Ana', 'resp@sicma.test'))
        self.assertEqual(datos['ubicacion_nombre'], 'Sala principal · Zona A')
        historial = self.auditor.get(f'/api/activos/{datos["id"]}/historial/').json()
        self.assertEqual([h['campo_modificado'] for h in historial], ['alta'])

    def test_editar_registra_cada_campo_cambiado(self):
        activo = self.alta().json()
        otra = Ubicacion.objects.create(sala='Sala B')

        respuesta = self.tecnico.patch(f'/api/activos/{activo["id"]}/', {
            'estado': 'En_mantenimiento', 'ubicacion': otra.id, 'nombre': 'Nodo MySQL 01',
        }, format='json')

        self.assertEqual(respuesta.status_code, 200)
        cambios = {h['campo_modificado']: (h['valor_anterior'], h['valor_nuevo'], h['usuario_nombre'])
                   for h in self.auditor.get(f'/api/activos/{activo["id"]}/historial/').json()}
        self.assertEqual(cambios['estado'], ('Operativo', 'En_mantenimiento', 'tecnico'))
        self.assertEqual(cambios['ubicacion'][1], 'Sala B')
        self.assertNotIn('nombre', cambios)  # sin cambio real, sin registro

    def test_codigo_y_serie_son_unicos(self):
        self.alta()
        repetido = self.alta(numero_serie='SN-002')
        serie = self.alta(codigo='mysql02')
        self.assertEqual((repetido.status_code, serie.status_code), (400, 400))
        self.assertIn('codigo', repetido.json())
        self.assertIn('numero_serie', serie.json())

    def test_rechaza_tipo_fuera_del_catalogo_y_ubicacion_desactivada(self):
        self.assertIn('tipo', self.alta(tipo='Tostadora').json())
        inactiva = Ubicacion.objects.create(sala='Bodega', activa=False)
        self.assertIn('ubicacion', self.alta(ubicacion=inactiva.id).json())

    def test_no_se_elimina_y_dar_de_baja_lo_oculta_del_listado(self):
        activo = self.alta().json()
        self.assertEqual(self.admin.delete(f'/api/activos/{activo["id"]}/').status_code, 405)

        self.tecnico.patch(f'/api/activos/{activo["id"]}/', {'estado': 'Retirado'}, format='json')

        self.assertEqual(self.auditor.get('/api/activos/').json(), [])
        todos = self.auditor.get('/api/activos/', {'incluir_retirados': 'true'}).json()
        self.assertEqual([a['estado'] for a in todos], ['Retirado'])

    def test_busqueda_y_filtros(self):
        otra = Ubicacion.objects.create(sala='Sala B')
        self.alta()
        self.alta(codigo='sw01', nombre='Switch core', tipo='Switch', numero_serie='SN-9', ubicacion=otra.id)

        def codigos(**filtros):
            return [a['codigo'] for a in self.auditor.get('/api/activos/', filtros).json()]

        self.assertEqual(codigos(q='core'), ['sw01'])
        self.assertEqual(codigos(q='sn-001'), ['mysql01'])
        self.assertEqual(codigos(tipo='Switch'), ['sw01'])
        self.assertEqual(codigos(ubicacion=self.sala.id), ['mysql01'])
        self.assertEqual(codigos(estado='Operativo'), ['mysql01', 'sw01'])

    def test_permisos_por_rol(self):
        self.assertEqual(self.alta(cliente=self.auditor).status_code, 403)
        self.assertEqual(self.alta(cliente=cliente_con_rol('jefe', 'Jefatura')).status_code, 403)
        self.assertEqual(self.alta(cliente=self.admin).status_code, 201)
        self.assertEqual(self.auditor.get('/api/activos/').status_code, 200)


class CatalogosTests(InventarioTestCase):
    def test_tipos_iniciales_y_administracion_del_catalogo(self):
        nombres = [t['nombre'] for t in self.auditor.get('/api/activos/tipos/').json()]
        self.assertIn('Servidor', nombres)
        self.assertEqual(self.tecnico.post('/api/activos/tipos/', {'nombre': 'PDU'}, format='json').status_code, 403)
        self.assertEqual(self.admin.post('/api/activos/tipos/', {'nombre': 'PDU'}, format='json').status_code, 201)

    def test_renombrar_un_tipo_actualiza_los_activos_y_desactivarlo_lo_oculta(self):
        activo = self.alta().json()
        servidor = TipoActivo.objects.get(nombre='Servidor')

        self.admin.patch(f'/api/activos/tipos/{servidor.id}/', {'nombre': 'Servidor físico'}, format='json')
        self.assertEqual(Activo.objects.get(pk=activo['id']).tipo, 'Servidor físico')

        self.admin.patch(f'/api/activos/tipos/{servidor.id}/', {'activo': False}, format='json')
        self.assertNotIn('Servidor físico', [t['nombre'] for t in self.auditor.get('/api/activos/tipos/').json()])
        # Un activo puede conservar un tipo que luego se desactivó.
        self.assertEqual(self.tecnico.patch(f'/api/activos/{activo["id"]}/', {'marca': 'HP'}, format='json').status_code, 200)

    def test_ubicaciones_alta_edicion_y_baja_logica(self):
        creada = self.admin.post('/api/ubicaciones/', {'sala': 'Sala B', 'zona': 'Pasillo frío'}, format='json')
        self.assertEqual(creada.status_code, 201)
        id_ = creada.json()['id']
        self.assertEqual(self.tecnico.patch(f'/api/ubicaciones/{id_}/', {'zona': 'X'}, format='json').status_code, 403)

        self.assertEqual(self.admin.patch(f'/api/ubicaciones/{id_}/', {'activa': False}, format='json').status_code, 200)
        self.assertNotIn(id_, [u['id'] for u in self.auditor.get('/api/ubicaciones/').json()])
        self.assertIn(id_, [u['id'] for u in self.auditor.get('/api/ubicaciones/', {'todas': '1'}).json()])

    def test_no_se_desactiva_una_ubicacion_en_uso(self):
        self.alta()
        respuesta = self.admin.patch(f'/api/ubicaciones/{self.sala.id}/', {'activa': False}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('activos sin retirar', respuesta.json()['activa'][0])

    def test_dispositivo_iot_alta_con_clave_unica_edicion_y_baja(self):
        creado = self.admin.post('/api/sensores/', {
            'codigo': 'esp32-02', 'tipo': 'DHT22', 'ubicacion': self.sala.id, 'intervalo_esperado_segundos': 60,
        }, format='json')
        self.assertEqual(creado.status_code, 201)
        clave = creado.json()['clave_dispositivo']
        sensor = Sensor.objects.get(codigo='esp32-02')
        self.assertTrue(check_password(clave, sensor.device_key_hash))
        self.assertNotIn('clave_dispositivo', self.auditor.get(f'/api/sensores/{sensor.id}/').json())

        nueva = self.admin.post(f'/api/sensores/{sensor.id}/clave/').json()['clave_dispositivo']
        sensor.refresh_from_db()
        self.assertFalse(check_password(clave, sensor.device_key_hash))
        self.assertTrue(check_password(nueva, sensor.device_key_hash))

        self.assertEqual(self.admin.patch(f'/api/sensores/{sensor.id}/', {'codigo': 'otro'}, format='json').status_code, 400)
        self.assertEqual(self.admin.patch(f'/api/sensores/{sensor.id}/', {'estado': 'Inactivo'}, format='json').json()['estado'], 'Inactivo')
        self.assertEqual(self.tecnico.patch(f'/api/sensores/{sensor.id}/', {'estado': 'Activo'}, format='json').status_code, 403)


@override_settings(ZABBIX_WEBHOOK_SECRET='secreto', ALERTAS_CORREO_ASINCRONO=False, DEFAULT_FROM_EMAIL='sicma@sicma.test')
class ZabbixActivoResponsableTests(InventarioTestCase):
    """RF-CAT-05 por activo: el problema de Zabbix se vincula al activo y se avisa a su responsable."""

    modelos = InventarioTestCase.modelos + (HostProblemaZabbix, Alerta, Notificacion)

    def enviar(self, host):
        with self.captureOnCommitCallbacks(execute=True):
            return APIClient().post('/api/integraciones/zabbix/webhook/', {
                'event_id': '700', 'host': host, 'problem': 'MySQL: Service is down',
                'severity': 'High', 'status': 'PROBLEM',
            }, format='json', HTTP_X_ZABBIX_TOKEN='secreto')

    def test_host_inventariado_se_vincula_y_avisa_al_responsable(self):
        activo = self.alta(responsable=self.responsable.id).json()

        self.assertEqual(self.enviar('MySQL01').status_code, 202)  # el código se compara sin mayúsculas

        self.assertEqual(HostProblemaZabbix.objects.get().activo_id, activo['id'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['resp@sicma.test'])
        self.assertIn('Activo: mysql01', mail.outbox[0].body)
        self.assertEqual(Notificacion.objects.get().resultado, 'Enviado')

    def test_host_sin_inventariar_registra_la_alerta_sin_correo(self):
        self.enviar('desconocido')
        self.assertIsNone(HostProblemaZabbix.objects.get().activo_id)
        self.assertEqual((Alerta.objects.count(), len(mail.outbox)), (1, 0))
