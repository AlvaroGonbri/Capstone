"""Consulta periódica de Zabbix (RF-INF-01) y conciliación de sus problemas (RF-INF-02).

`sincronizar()` la ejecuta el comando `manage.py sincronizar_zabbix` cada minuto. Guarda una
foto del estado en EstadoInfraestructura y registra los problemas nuevos o resueltos que el
webhook no haya alcanzado a avisar (por ejemplo, si SICMA estaba detenido).
"""
from collections import Counter
from datetime import timedelta
import logging
from typing import Any

from django.utils import timezone

import requests

from alertas.models import HostProblemaZabbix
from alertas.zabbix import registrar_evento_zabbix

from .models import EstadoInfraestructura
from .zabbix_client import SEVERIDADES, ZabbixClient, ZabbixError


logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 60
# Si la última sincronización exitosa es más antigua, las vistas consultan Zabbix en directo.
ANTIGUEDAD_MAXIMA = timedelta(seconds=3 * INTERVALO_SEGUNDOS)
GRUPOS_MONITOREADOS = ['Cluster', 'Hypervisores']


# ---------------------------------------------------------------- consultas

def consultar_activos(cliente: ZabbixClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hosts de Cluster e Hypervisores con el formato de Activo del frontend, y sus problemas abiertos.

    Cada problema abierto trae el nombre técnico del host, que es el que se compara con el
    código del activo en el inventario.
    """
    grupos = cliente.obtener_grupos(GRUPOS_MONITOREADOS)
    groupids = [str(grupo['groupid']) for grupo in grupos]
    if not groupids:
        return [], []

    hosts = cliente.obtener_hosts(groupids)
    hostids = [str(host['hostid']) for host in hosts]
    items = cliente.obtener_items_mysql(hostids)
    # problem.get con recent=True incluye los recién resueltos; abiertos = sin r_eventid.
    problemas = [p for p in cliente.obtener_problemas(hostids) if str(p.get('r_eventid', '0')) == '0']

    eventos = cliente.obtener_eventos_con_hosts([str(p['eventid']) for p in problemas])
    host_por_evento = {
        str(evento['eventid']): evento['hosts'][0]
        for evento in eventos
        if evento.get('hosts')
    }
    problemas_por_host = Counter(
        str(host_por_evento[str(p['eventid'])]['hostid'])
        for p in problemas
        if str(p['eventid']) in host_por_evento
    )
    items_por_host: dict[str, dict[str, dict[str, Any]]] = {}
    for item in items:
        items_por_host.setdefault(str(item['hostid']), {})[item['key_']] = item

    activos = [_serializar_host(host, items_por_host, problemas_por_host) for host in hosts]
    abiertos = [
        {
            'evento_id': str(p['eventid']),
            'host': host_por_evento.get(str(p['eventid']), {}).get('host') or '',
            'problema': p.get('name') or '',
            'severidad': SEVERIDADES.get(str(p.get('severity')), str(p.get('severity', ''))),
        }
        for p in problemas
    ]
    return activos, abiertos


def consultar_estado(cliente: ZabbixClient) -> dict[str, Any]:
    return {
        'cluster': cliente.estado_cluster('Cluster'),
        'problemas': cliente.problemas(min_severidad=2),
    }


def _serializar_host(
    host: dict[str, Any],
    items_por_host: dict[str, dict[str, dict[str, Any]]],
    problemas_por_host: Counter[str],
) -> dict[str, Any]:
    hostid = str(host['hostid'])
    interfaces = host.get('interfaces') or []
    interfaz = interfaces[0] if interfaces else {}
    grupos = [grupo['name'] for grupo in host.get('groups', [])]
    items = items_por_host.get(hostid, {})
    online = items.get('mysql.gr.online', {}).get('lastvalue')
    primary = items.get('mysql.gr.primary', {}).get('lastvalue')
    disponible = host.get('status') == '0' and (
        host.get('available') in (None, '0', '1') or host.get('available') == '1'
    )
    if host.get('maintenance_status') == '1':
        estado = 'en mantencion'
    else:
        estado = 'operativo' if disponible and online != '0' else 'en falla'
    return {
        'id': int(hostid),
        'codigo': host.get('host') or hostid,
        'nombre': host.get('name') or host.get('host') or hostid,
        'tipo': 'servidor',
        'grupo': grupos,
        'estado': estado,
        'direccion': interfaz.get('ip') or interfaz.get('dns') or 'Sin interfaz',
        'puerto': int(interfaz['port']) if str(interfaz.get('port', '')).isdigit() else None,
        'mantenimiento': host.get('maintenance_status') == '1',
        'problemasActivos': problemas_por_host[hostid],
        'mysqlGrupoOnline': online == '1' if online is not None else None,
        'mysqlEsPrimario': primary == '1' if primary is not None else None,
        'ultimoError': host.get('error') or interfaz.get('error') or None,
    }


# ------------------------------------------------------------ sincronización

def conciliar_problemas(abiertos: list[dict[str, Any]]) -> dict[str, int]:
    """Registra los problemas abiertos que SICMA no conoce y cierra los que Zabbix ya resolvió."""
    conocidos = set(
        HostProblemaZabbix.objects.filter(estado='PROBLEM').values_list('identificador_externo', flat=True)
    )
    ids_abiertos = {p['evento_id'] for p in abiertos}

    nuevos = [p for p in abiertos if p['evento_id'] not in conocidos]
    for p in nuevos:
        registrar_evento_zabbix(p['evento_id'], p['host'], p['problema'], p['severidad'], 'PROBLEM')

    resueltos = conocidos - ids_abiertos
    for event_id in resueltos:
        registrar_evento_zabbix(event_id, '', '', '', 'RESOLVED')

    return {'nuevos': len(nuevos), 'resueltos': len(resueltos)}


def sincronizar(cliente: ZabbixClient | None = None) -> dict[str, Any]:
    """Una pasada: consulta Zabbix, guarda la foto y concilia los problemas.

    Si Zabbix no responde, se registra el error y se conserva la última foto buena.
    """
    foto = EstadoInfraestructura.get_solo()
    ahora = timezone.now()
    foto.ultimo_intento = ahora
    try:
        cliente = cliente or ZabbixClient()
        activos, abiertos = consultar_activos(cliente)
        estado = consultar_estado(cliente)
        hosts = cliente.hosts()
    except (ZabbixError, requests.RequestException) as error:
        foto.error = str(error)[:2000]
        foto.save(update_fields=['ultimo_intento', 'error'])
        logger.warning('No fue posible sincronizar con Zabbix: %s', error)
        return {'exitosa': False, 'error': foto.error}

    conciliados = conciliar_problemas(abiertos)
    foto.activos, foto.estado, foto.hosts = activos, estado, hosts
    foto.ultima_exitosa = ahora
    foto.error = ''
    foto.save(update_fields=['ultimo_intento', 'ultima_exitosa', 'error', 'activos', 'estado', 'hosts'])
    return {'exitosa': True, 'hosts': len(activos), 'problemas_abiertos': len(abiertos), **conciliados}


def foto_vigente(campo: str) -> Any:
    """Datos de la última foto si es reciente y ningún webhook la dejó vieja; si no, None."""
    foto = EstadoInfraestructura.objects.filter(pk=1).first()
    if not foto or not foto.ultima_exitosa or getattr(foto, campo) is None:
        return None
    if timezone.now() - foto.ultima_exitosa > ANTIGUEDAD_MAXIMA:
        return None
    if foto.ultimo_webhook and foto.ultimo_webhook >= foto.ultima_exitosa:
        return None
    return getattr(foto, campo)


def marcar_webhook() -> None:
    EstadoInfraestructura.objects.update_or_create(pk=1, defaults={'ultimo_webhook': timezone.now()})
