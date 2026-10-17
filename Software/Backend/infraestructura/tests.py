from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from infraestructura.zabbix_client import ZabbixClient


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
