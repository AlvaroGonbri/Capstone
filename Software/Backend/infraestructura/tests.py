from datetime import timedelta
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from alertas.models import Alerta, HostProblemaZabbix, Notificacion
from infraestructura.models import EstadoInfraestructura
from infraestructura.sincronizacion import foto_vigente, sincronizar
from infraestructura.zabbix_client import ZabbixClient, ZabbixError
from inventario.models import Activo
from mediciones.models import Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol


class ZabbixClientGruposTests(TestCase):
    @patch('infraestructura.zabbix_client.requests.post')
    def test_obtener_grupos_no_distingue_mayusculas(self, post):
        post.return_value = Mock(json=lambda: {'result': [
            {'groupid': '1', 'name': 'Cluster'},
            {'groupid': '2', 'name': 'hypervisores'},
            {'groupid': '3', 'name': 'Zabbix servers'},
        ]}, raise_for_status=lambda: None)

        cliente = ZabbixClient(url='http://zabbix.test/api_jsonrpc.php', token='token-de-prueba')
        grupos = cliente.obtener_grupos(['Cluster', 'Hypervisores'])

        self.assertEqual([grupo['groupid'] for grupo in grupos], ['1', '2'])


class ActivosZabbixViewTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        usuario = get_user_model().objects.create_user(username='prueba', password='clave')
        usuario.groups.set([Group.objects.get_or_create(name='Tecnico')[0]])
        self.cliente.force_authenticate(usuario)

    @override_settings(
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
        ZABBIX_URL='http://zabbix.test/api_jsonrpc.php',
        ZABBIX_TOKEN='token-de-prueba',
    )
    @patch('infraestructura.zabbix_client.requests.post')
    def test_consulta_activos_usa_json_rpc_y_convierte_datos(self, post):
        post.side_effect = [
            Mock(json=lambda: {'result': [{'groupid': '1', 'name': 'Cluster'}]}, raise_for_status=lambda: None),
            Mock(json=lambda: {'result': [{
                'hostid': '7', 'host': 'mysql-01', 'name': 'MySQL 01', 'status': '0',
                'available': '1', 'error': '', 'maintenance_status': '0',
                'groups': [{'groupid': '1', 'name': 'Cluster'}],
                'interfaces': [{'ip': '10.0.0.7', 'port': '10050', 'available': '1', 'error': ''}],
            }]}, raise_for_status=lambda: None),
            Mock(json=lambda: {'result': [
                {'hostid': '7', 'key_': 'mysql.gr.online', 'lastvalue': '1'},
                {'hostid': '7', 'key_': 'mysql.gr.primary', 'lastvalue': '1'},
            ]}, raise_for_status=lambda: None),
            Mock(json=lambda: {'result': [{'eventid': '99'}]}, raise_for_status=lambda: None),
            Mock(json=lambda: {'result': [{'eventid': '99', 'hosts': [{'hostid': '7'}]}]}, raise_for_status=lambda: None),
        ]

        respuesta = self.cliente.get('/api/infraestructura/activos/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()[0]['id'], 7)
        self.assertTrue(respuesta.json()[0]['mysqlEsPrimario'])
        self.assertEqual(post.call_args_list[0].kwargs['headers']['Content-Type'], 'application/json-rpc')
        self.assertEqual(post.call_args_list[0].kwargs['json']['jsonrpc'], '2.0')
        self.assertEqual(post.call_args_list[0].kwargs['timeout'], 10)


def respuesta_zabbix(resultado):
    return Mock(json=lambda: {'result': resultado}, raise_for_status=lambda: None)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    ZABBIX_URL='http://zabbix.test/api_jsonrpc.php',
    ZABBIX_TOKEN='token-de-prueba',
)
class EventosHostViewTests(TestCase):
    url = '/api/infraestructura/hosts/10683/eventos/'

    def setUp(self):
        self.cliente = APIClient()
        usuario = get_user_model().objects.create_user(username='auditor', password='clave')
        usuario.groups.set([Group.objects.get_or_create(name='Auditor')[0]])
        self.cliente.force_authenticate(usuario)

    @patch('infraestructura.zabbix_client.requests.post')
    def test_historial_incluye_problemas_activos_y_resueltos(self, post):
        post.side_effect = [
            respuesta_zabbix([
                {'eventid': '20', 'clock': '1700000600', 'name': 'Agente caído', 'severity': '3',
                 'acknowledged': '0', 'r_eventid': '0'},
                {'eventid': '10', 'clock': '1700000000', 'name': 'MySQL Router caído', 'severity': '4',
                 'acknowledged': '1', 'r_eventid': '11'},
            ]),
            respuesta_zabbix([{'eventid': '11', 'clock': '1700000180'}]),
        ]

        respuesta = self.cliente.get(self.url, {'dias': 7})

        self.assertEqual(respuesta.status_code, 200)
        activo, resuelto = respuesta.json()
        self.assertEqual((activo['estado'], activo['fin'], activo['duracion_segundos']), ('activo', None, None))
        self.assertEqual((resuelto['estado'], resuelto['duracion_segundos']), ('resuelto', 180))
        self.assertEqual(resuelto['severidad'], 'Alta')
        self.assertTrue(resuelto['reconocido'])
        params = post.call_args_list[0].kwargs['json']['params']
        self.assertEqual((params['hostids'], params['value']), (['10683'], 1))
        self.assertEqual(post.call_args_list[1].kwargs['json']['params']['eventids'], ['11'])

    @patch('infraestructura.zabbix_client.requests.post')
    def test_sin_problemas_no_busca_cierres(self, post):
        post.return_value = respuesta_zabbix([])
        self.assertEqual(self.cliente.get(self.url).json(), [])
        self.assertEqual(post.call_count, 1)

    def test_dias_fuera_de_rango_responde_400(self):
        for valor in ('0', '366', 'abc'):
            self.assertEqual(self.cliente.get(self.url, {'dias': valor}).status_code, 400)

    def test_usuario_sin_rol_no_puede_consultar(self):
        cliente = APIClient()
        cliente.force_authenticate(get_user_model().objects.create_user(username='sinrol', password='clave'))
        self.assertEqual(cliente.get(self.url).status_code, 403)


class ZabbixFalso:
    """Cliente de Zabbix en memoria para probar la sincronización sin red."""

    def __init__(self, problemas=(), falla=None):
        self.problemas_abiertos = list(problemas)
        self.falla = falla

    def obtener_grupos(self, nombres):
        if self.falla:
            raise self.falla
        return [{'groupid': '1', 'name': 'Cluster'}]

    def obtener_hosts(self, groupids):
        return [{
            'hostid': '7', 'host': 'mysql01', 'name': 'MySQL 01', 'status': '0', 'available': '1',
            'error': '', 'maintenance_status': '0', 'groups': [{'groupid': '1', 'name': 'Cluster'}],
            'interfaces': [{'ip': '10.0.0.7', 'port': '10050', 'available': '1', 'error': ''}],
        }]

    def obtener_items_mysql(self, hostids):
        return [{'hostid': '7', 'key_': 'mysql.gr.online', 'lastvalue': '1'}]

    def obtener_problemas(self, hostids):
        # Como problem.get con recent=True: también trae uno recién resuelto, que se descarta.
        return self.problemas_abiertos + [{'eventid': '1', 'name': 'Viejo', 'severity': '4', 'r_eventid': '2'}]

    def obtener_eventos_con_hosts(self, eventids):
        return [{'eventid': e, 'hosts': [{'hostid': '7', 'host': 'mysql01', 'name': 'MySQL 01'}]} for e in eventids]

    def estado_cluster(self, grupo):
        return {'nodos': [], 'primario': None, 'nodos_online': 0}

    def problemas(self, min_severidad=2):
        return []

    def hosts(self, grupo=None):
        return [{'id': '7', 'nombre': 'MySQL 01', 'habilitado': True, 'ip': '10.0.0.7', 'agente': 'disponible'}]


def problema(eventid, nombre='MySQL: Service is down', severidad='4'):
    return {'eventid': eventid, 'name': nombre, 'severity': severidad, 'r_eventid': '0'}


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    ZABBIX_WEBHOOK_SECRET='secreto',
    ALERTAS_CORREO_ASINCRONO=False,
)
class SincronizacionZabbixTests(TablasNoGestionadasTestCase):
    """RF-INF-01: la consulta periódica guarda el estado y concilia los problemas."""

    modelos = TablasNoGestionadasTestCase.modelos + (Activo, HostProblemaZabbix, Alerta, Notificacion)

    def setUp(self):
        self.auditor = cliente_con_rol('auditor', 'Auditor')

    def test_guarda_la_foto_y_las_vistas_la_usan_sin_consultar_zabbix(self):
        resultado = sincronizar(ZabbixFalso([problema('50')]))

        self.assertEqual((resultado['exitosa'], resultado['hosts'], resultado['nuevos']), (True, 1, 1))
        with patch('infraestructura.zabbix_client.requests.post') as post:
            activos = self.auditor.get('/api/infraestructura/activos/').json()
            self.assertEqual(self.auditor.get('/api/infraestructura/hosts/').json()[0]['nombre'], 'MySQL 01')
            post.assert_not_called()
        self.assertEqual((activos[0]['codigo'], activos[0]['problemasActivos']), ('mysql01', 1))
        estado = self.auditor.get('/api/infraestructura/sincronizacion/').json()
        self.assertEqual((estado['al_dia'], estado['error'], estado['intervalo_segundos']), (True, None, 60))

    def test_registra_problemas_que_el_webhook_no_aviso_y_cierra_los_resueltos(self):
        sincronizar(ZabbixFalso([problema('50'), problema('51', 'Agente caído', '2')]))

        self.assertEqual(
            set(HostProblemaZabbix.objects.values_list('identificador_externo', 'estado')),
            {('50', 'PROBLEM'), ('51', 'PROBLEM')},
        )
        self.assertEqual(Alerta.objects.get(host_problema_zabbix__identificador_externo='50').severidad, 'Alta')
        self.assertFalse(HostProblemaZabbix.objects.filter(identificador_externo='1').exists())

        # Una segunda pasada igual no duplica nada.
        self.assertEqual(sincronizar(ZabbixFalso([problema('50'), problema('51')]))['nuevos'], 0)
        self.assertEqual(Alerta.objects.count(), 2)

        # El 51 se resolvió en Zabbix sin que llegara el webhook de recuperación.
        resultado = sincronizar(ZabbixFalso([problema('50')]))
        self.assertEqual(resultado['resueltos'], 1)
        self.assertEqual(HostProblemaZabbix.objects.get(identificador_externo='51').estado, 'RESOLVED')
        self.assertEqual(Alerta.objects.get(host_problema_zabbix__identificador_externo='51').estado, 'Cerrada')

    def test_si_zabbix_no_responde_conserva_la_ultima_foto_y_registra_el_error(self):
        sincronizar(ZabbixFalso())
        resultado = sincronizar(ZabbixFalso(falla=ZabbixError('sin conexión')))

        self.assertFalse(resultado['exitosa'])
        foto = EstadoInfraestructura.get_solo()
        self.assertEqual((foto.error, foto.activos[0]['codigo']), ('sin conexión', 'mysql01'))
        self.assertEqual(self.auditor.get('/api/infraestructura/sincronizacion/').json()['error'], 'sin conexión')

    def test_foto_vieja_o_posterior_a_un_webhook_se_ignora(self):
        sincronizar(ZabbixFalso())
        self.assertIsNotNone(foto_vigente('activos'))

        APIClient().post('/api/integraciones/zabbix/webhook/', {
            'event_id': '60', 'host': 'mysql01', 'problem': 'X', 'severity': 'High', 'status': 'PROBLEM',
        }, format='json', HTTP_X_ZABBIX_TOKEN='secreto')
        self.assertIsNone(foto_vigente('activos'))

        sincronizar(ZabbixFalso([problema('60')]))
        self.assertIsNotNone(foto_vigente('activos'))
        EstadoInfraestructura.objects.update(ultima_exitosa=timezone.now() - timedelta(minutes=4))
        self.assertIsNone(foto_vigente('activos'))
        self.assertFalse(self.auditor.get('/api/infraestructura/sincronizacion/').json()['al_dia'])

    @override_settings(ALERTAS_CORREO_ASINCRONO=True, DEFAULT_FROM_EMAIL='sicma@sicma.test')
    def test_comando_una_vez_envia_el_correo_antes_de_terminar(self):
        responsable = get_user_model().objects.create_user(username='resp', email='resp@sicma.test', password='x')
        Activo.objects.create(
            codigo='mysql01', nombre='Nodo 01', numero_serie='SN-1', ubicacion=Ubicacion.objects.create(sala='A'),
            fecha_alta=timezone.now(), responsable=responsable,
        )
        salida = StringIO()
        # Fuera de los tests, on_commit corre al confirmar cada evento, es decir, durante la pasada.
        with patch('infraestructura.sincronizacion.ZabbixClient', return_value=ZabbixFalso([problema('70')])),                 patch('alertas.zabbix.transaction.on_commit', side_effect=lambda funcion: funcion()):
            call_command('sincronizar_zabbix', '--una-vez', stdout=salida)

        self.assertIn('OK: 1 hosts', salida.getvalue())
        self.assertEqual([m.to for m in mail.outbox], [['resp@sicma.test']])  # enviado en línea, no en un hilo
        self.assertTrue(settings.ALERTAS_CORREO_ASINCRONO)  # el ajuste se restaura al terminar
