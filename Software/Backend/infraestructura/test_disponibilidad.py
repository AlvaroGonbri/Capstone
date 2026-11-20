"""Estado de los servidores según Zabbix 7: un servidor apagado nunca debe verse "operativo".

Casos tomados del Zabbix real del proyecto (2026-11-19): mysql02 apagado (agente sin responder, su
último dato de hace 22 h) aparecía operativo, y mysql01/mysql03 encendidos aparecían en falla porque
su ítem mysql.gr.online estaba "no soportado" (Zabbix lo deja en 0).
"""
import time
from collections import Counter

from django.test import SimpleTestCase

from .sincronizacion import _serializar_host
from .zabbix_client import VIGENCIA_DATO_SEGUNDOS, disponibilidad, valor_vigente

AHORA = time.time()


def host(interfaces=('1',), activo='0', status='0', mantencion='0', error=''):
    """Host como lo entrega host.get de Zabbix 7 (sin host.available, que ya no existe)."""
    return {
        'hostid': '7', 'host': 'mysql02', 'name': 'mysql02', 'status': status,
        'active_available': activo, 'maintenance_status': mantencion,
        'groups': [{'groupid': '1', 'name': 'Cluster'}],
        'interfaces': [{'ip': '10.0.0.7', 'port': '10050', 'type': '1', 'main': '1', 'available': a, 'error': error}
                       for a in interfaces],
    }


def item(clave, valor, hace_segundos=30, soportado=True):
    return {'hostid': '7', 'key_': clave, 'lastvalue': valor,
            'lastclock': str(int(AHORA - hace_segundos)), 'state': '0' if soportado else '1'}


def estado(h, items=()):
    return _serializar_host(h, {'7': {i['key_']: i for i in items}}, Counter())


class DisponibilidadTests(SimpleTestCase):
    def test_interfaz_no_disponible(self):
        self.assertEqual(disponibilidad(host(interfaces=('2',))), 'no disponible')

    def test_agente_activo_no_disponible_aunque_la_interfaz_pasiva_responda(self):
        self.assertEqual(disponibilidad(host(interfaces=('1',), activo='2')), 'no disponible')

    def test_disponible(self):
        self.assertEqual(disponibilidad(host(interfaces=('1',), activo='1')), 'disponible')

    def test_sin_informacion_es_desconocido_no_disponible(self):
        self.assertEqual(disponibilidad(host(interfaces=('0',), activo='0')), 'desconocido')
        self.assertEqual(disponibilidad(host(interfaces=())), 'desconocido')

    def test_host_deshabilitado(self):
        self.assertEqual(disponibilidad(host(status='1')), 'desconocido')


class ValorVigenteTests(SimpleTestCase):
    def test_reciente_y_soportado(self):
        self.assertEqual(valor_vigente(item('mysql.gr.online', '1'), AHORA), '1')

    def test_dato_viejo_es_desconocido(self):
        viejo = item('mysql.gr.online', '1', hace_segundos=VIGENCIA_DATO_SEGUNDOS + 60)
        self.assertIsNone(valor_vigente(viejo, AHORA))

    def test_item_no_soportado_es_desconocido(self):
        self.assertIsNone(valor_vigente(item('mysql.gr.online', '0', soportado=False), AHORA))

    def test_nunca_medido_es_desconocido(self):
        self.assertIsNone(valor_vigente({'lastvalue': '0', 'lastclock': '0', 'state': '0'}, AHORA))


class EstadoServidorTests(SimpleTestCase):
    def test_servidor_apagado_con_ultimo_dato_de_hace_22_horas_esta_en_falla(self):
        apagado = host(interfaces=('2',), activo='2', error='Get value from agent failed: Cannot establish TCP connection')
        r = estado(apagado, [item('mysql.gr.online', '1', hace_segundos=22 * 3600)])
        self.assertEqual(r['estado'], 'en falla')
        self.assertEqual(r['disponibilidad'], 'no disponible')
        self.assertIsNone(r['mysqlGrupoOnline'])  # el "1" de hace 22 horas no vale
        self.assertIn('Cannot establish TCP connection', r['ultimoError'])

    def test_sin_error_de_zabbix_igual_explica_la_falla(self):
        self.assertEqual(estado(host(interfaces=('2',)))['ultimoError'], 'El agente de Zabbix no responde.')

    def test_item_no_soportado_no_marca_en_falla_a_un_servidor_encendido(self):
        r = estado(host(interfaces=('1',), activo='1'), [item('mysql.gr.online', '0', soportado=False)])
        self.assertEqual(r['estado'], 'operativo')
        self.assertIsNone(r['mysqlGrupoOnline'])

    def test_nodo_fuera_del_grupo_con_dato_reciente_esta_en_falla(self):
        r = estado(host(interfaces=('1',)), [item('mysql.gr.online', '0')])
        self.assertEqual(r['estado'], 'en falla')
        self.assertFalse(r['mysqlGrupoOnline'])

    def test_operativo(self):
        r = estado(host(interfaces=('1',)), [item('mysql.gr.online', '1'), item('mysql.gr.primary', '1')])
        self.assertEqual(r['estado'], 'operativo')
        self.assertTrue(r['mysqlGrupoOnline'])
        self.assertTrue(r['mysqlEsPrimario'])

    def test_en_mantencion_tiene_prioridad(self):
        self.assertEqual(estado(host(interfaces=('2',), mantencion='1'))['estado'], 'en mantencion')

    def test_deshabilitado_en_zabbix(self):
        r = estado(host(status='1'))
        self.assertEqual(r['estado'], 'en falla')
        self.assertIn('Deshabilitado', r['ultimoError'])
