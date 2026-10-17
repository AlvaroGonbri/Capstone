"""
Cliente de solo lectura de la API JSON-RPC de Zabbix para SICMA.

Configuración (settings.py, desde variables de entorno):
    ZABBIX_URL    http://192.168.100.121/zabbix/api_jsonrpc.php
    ZABBIX_TOKEN  API token del usuario sicma_api
"""
from datetime import datetime, timezone
from typing import Any

import requests
from django.conf import settings


SEVERIDADES = {
    '0': 'No clasificado',
    '1': 'Información',
    '2': 'Advertencia',
    '3': 'Media',
    '4': 'Alta',
    '5': 'Desastre',
}

# interface.available en Zabbix: 0 = desconocido, 1 = disponible, 2 = no disponible
DISPONIBILIDAD = {'0': 'desconocido', '1': 'disponible', '2': 'no disponible'}


class ZabbixError(Exception):
    """Error devuelto por la API JSON-RPC de Zabbix."""


def _fecha(clock: Any) -> str | None:
    clock = int(clock or 0)
    if not clock:
        return None
    return datetime.fromtimestamp(clock, tz=timezone.utc).isoformat()


class ZabbixClient:
    """Cliente único para las consultas de solo lectura de Zabbix."""

    METODOS_PERMITIDOS = {
        'host.get',
        'hostgroup.get',
        'item.get',
        'problem.get',
        'event.get',
        'history.get',
        'trend.get',
    }

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.url = url or getattr(settings, 'ZABBIX_URL', '')
        self.token = token or getattr(settings, 'ZABBIX_TOKEN', '')
        self.timeout = timeout
        self._id = 0
        if not self.url:
            raise ZabbixError('La variable ZABBIX_URL no está configurada.')
        if not self.token:
            raise ZabbixError('La variable ZABBIX_TOKEN no está configurada.')

    def _llamar(self, metodo: str, params: dict[str, Any]) -> Any:
        if metodo not in self.METODOS_PERMITIDOS:
            raise ZabbixError(f'El método de Zabbix no está permitido: {metodo}.')

        self._id += 1
        respuesta = requests.post(
            self.url,
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json-rpc',
            },
            json={
                'jsonrpc': '2.0',
                'method': metodo,
                'params': params,
                'id': self._id,
            },
            timeout=self.timeout,
        )
        respuesta.raise_for_status()
        cuerpo = respuesta.json()
        if 'error' in cuerpo:
            error = cuerpo['error']
            detalle = error.get('data') or error.get('message') or 'Error desconocido.'
            raise ZabbixError(f'Zabbix rechazó {metodo}: {detalle}')
        if 'result' not in cuerpo:
            raise ZabbixError(f'Respuesta inválida de Zabbix para {metodo}.')
        return cuerpo['result']

    # ---------- Consultas crudas (usadas por /api/infraestructura/activos/) ----------

    def obtener_grupos(self, nombres: list[str]) -> list[dict[str, Any]]:
        """Grupos por nombre, sin distinguir mayúsculas ('hypervisores' == 'Hypervisores').

        El filter de Zabbix compara exacto, así que se filtra aquí sobre los grupos
        visibles para el usuario de la API.
        """
        buscados = {nombre.casefold() for nombre in nombres}
        grupos = self._llamar('hostgroup.get', {'output': ['groupid', 'name']})
        return [grupo for grupo in grupos if grupo['name'].casefold() in buscados]

    def obtener_hosts(self, groupids: list[str]) -> list[dict[str, Any]]:
        return self._llamar(
            'host.get',
            {
                'output': [
                    'hostid',
                    'host',
                    'name',
                    'status',
                    'available',
                    'error',
                    'maintenance_status',
                ],
                'groupids': groupids,
                'selectGroups': ['groupid', 'name'],
                'selectInterfaces': ['interfaceid', 'ip', 'dns', 'port', 'type', 'available', 'error'],
                'sortfield': 'name',
            },
        )

    def obtener_items_mysql(self, hostids: list[str]) -> list[dict[str, Any]]:
        if not hostids:
            return []
        return self._llamar(
            'item.get',
            {
                'output': [
                    'itemid',
                    'hostid',
                    'key_',
                    'lastvalue',
                    'value_type',
                    'lastclock',
                    'name',
                ],
                'hostids': hostids,
                'search': {'key_': 'mysql.gr.'},
                'searchByAny': True,
            },
        )

    def obtener_problemas(self, hostids: list[str]) -> list[dict[str, Any]]:
        if not hostids:
            return []
        return self._llamar(
            'problem.get',
            {
                'output': ['eventid', 'severity', 'name', 'clock', 'r_eventid'],
                'hostids': hostids,
                'recent': True,
                'sortfield': ['eventid'],
                'sortorder': 'DESC',
                'limit': 1000,
            },
        )

    def obtener_eventos_con_hosts(self, eventids: list[str]) -> list[dict[str, Any]]:
        if not eventids:
            return []
        return self._llamar(
            'event.get',
            {
                'output': ['eventid'],
                'eventids': eventids,
                'selectHosts': ['hostid', 'host', 'name'],
            },
        )

    # ---------- Consultas de alto nivel ----------

    def hosts(self, grupo: str | None = None) -> list[dict[str, Any]]:
        """Hosts monitoreados, con su IP y si el agente responde."""
        params: dict[str, Any] = {
            'output': ['hostid', 'host', 'name', 'status'],
            'selectInterfaces': ['ip', 'available'],
        }
        if grupo:
            params['groupids'] = [g['groupid'] for g in self.obtener_grupos([grupo])]
            if not params['groupids']:
                return []
        resultado = []
        for host in self._llamar('host.get', params):
            interfaz = host['interfaces'][0] if host['interfaces'] else {}
            resultado.append({
                'id': host['hostid'],
                'nombre': host['name'],
                'habilitado': host['status'] == '0',
                'ip': interfaz.get('ip'),
                'agente': DISPONIBILIDAD.get(interfaz.get('available', '0')),
            })
        return resultado

    def problemas(self, min_severidad: int = 2) -> list[dict[str, Any]]:
        """Problemas activos (sin resolver), del más reciente al más antiguo."""
        problemas = self._llamar('problem.get', {
            'output': ['eventid', 'name', 'severity', 'clock', 'acknowledged'],
            'severities': list(range(min_severidad, 6)),
            'sortfield': ['eventid'],
            'sortorder': 'DESC',
        })
        if not problemas:
            return []

        # problem.get no trae el host: se obtiene desde los eventos
        eventos = self.obtener_eventos_con_hosts([p['eventid'] for p in problemas])
        host_de = {
            e['eventid']: (e['hosts'][0]['name'] if e.get('hosts') else None)
            for e in eventos
        }

        return [{
            'evento_id': p['eventid'],
            'host': host_de.get(p['eventid']),
            'problema': p['name'],
            'severidad': SEVERIDADES.get(p['severity'], p['severity']),
            'severidad_num': int(p['severity']),
            'desde': _fecha(p['clock']),
            'reconocido': p['acknowledged'] == '1',
        } for p in problemas]

    def eventos_host(self, hostid: str, desde_ts: int, limite: int = 200) -> list[dict[str, Any]]:
        """Historial de problemas de un host (RF-INF-03), del más reciente al más antiguo.

        Incluye los resueltos: Zabbix guarda el historial, SICMA solo lo consulta.
        """
        problemas = self._llamar('event.get', {
            'output': ['eventid', 'clock', 'name', 'severity', 'acknowledged', 'r_eventid'],
            'hostids': [hostid],
            'source': 0,  # eventos de triggers
            'object': 0,
            'value': 1,  # solo la apertura del problema; el cierre se busca por r_eventid
            'time_from': int(desde_ts),
            'sortfield': ['clock', 'eventid'],
            'sortorder': 'DESC',
            'limit': limite,
        })
        r_eventids = [p['r_eventid'] for p in problemas if p['r_eventid'] != '0']
        cierres = {}
        if r_eventids:
            cierres = {
                e['eventid']: int(e['clock'])
                for e in self._llamar('event.get', {'output': ['eventid', 'clock'], 'eventids': r_eventids})
            }

        resultado = []
        for p in problemas:
            inicio = int(p['clock'])
            fin = cierres.get(p['r_eventid'])
            resultado.append({
                'evento_id': p['eventid'],
                'problema': p['name'],
                'severidad': SEVERIDADES.get(p['severity'], p['severity']),
                'severidad_num': int(p['severity']),
                'inicio': _fecha(inicio),
                'fin': _fecha(fin),
                'estado': 'resuelto' if p['r_eventid'] != '0' else 'activo',
                'duracion_segundos': fin - inicio if fin else None,
                'reconocido': p['acknowledged'] == '1',
            })
        return resultado

    def estado_cluster(self, grupo: str = 'Cluster') -> dict[str, Any]:
        """Estado de cada nodo del InnoDB Cluster (items mysql.gr.online / mysql.gr.primary)."""
        items = self._llamar('item.get', {
            'output': ['key_', 'lastvalue', 'lastclock'],
            'selectHosts': ['name'],
            'group': grupo,
            'filter': {'key_': ['mysql.gr.online', 'mysql.gr.primary']},
        })
        nodos: dict[str, dict[str, Any]] = {}
        for item in items:
            nombre = item['hosts'][0]['name']
            nodo = nodos.setdefault(
                nombre,
                {'nodo': nombre, 'online': False, 'primario': False, 'ultima_lectura': None},
            )
            campo = 'online' if item['key_'] == 'mysql.gr.online' else 'primario'
            nodo[campo] = item['lastvalue'] == '1'
            nodo['ultima_lectura'] = _fecha(item['lastclock']) or nodo['ultima_lectura']

        lista = sorted(nodos.values(), key=lambda n: n['nodo'])
        primario = next((n['nodo'] for n in lista if n['primario']), None)
        return {
            'nodos': lista,
            'primario': primario,
            'nodos_online': sum(n['online'] for n in lista),
        }

    def historial(
        self,
        host: str,
        key: str,
        desde_ts: int,
        hasta_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        """Valores históricos de una métrica (para gráficos o BI)."""
        items = self._llamar('item.get', {
            'output': ['itemid', 'value_type'],
            'host': host,
            'filter': {'key_': key},
        })
        if not items:
            return []
        item = items[0]
        params: dict[str, Any] = {
            'output': 'extend',
            'itemids': item['itemid'],
            'history': int(item['value_type']),
            'time_from': int(desde_ts),
            'sortfield': 'clock',
            'sortorder': 'ASC',
        }
        if hasta_ts:
            params['time_till'] = int(hasta_ts)
        return [
            {'fecha': _fecha(v['clock']), 'valor': v['value']}
            for v in self._llamar('history.get', params)
        ]
