from collections import Counter
from collections.abc import Callable
import hmac
import time
from typing import Any

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

import requests

from alertas.zabbix import registrar_evento_zabbix
from login.permissions import READ_ROLES, RolePermission

from .serializers import EventoZabbixSerializer
from .zabbix_client import ZabbixClient, ZabbixError


CACHE_SEGUNDOS = 30  # evita consultar Zabbix en cada request del frontend
CACHE_ACTIVOS = 'infraestructura:activos'
CACHE_ESTADO = 'infraestructura:estado'
CACHE_HOSTS = 'infraestructura:hosts'


def _consultar(clave_cache: str, funcion: Callable[[ZabbixClient], Any]) -> Response:
    """Devuelve los datos en caché o consulta Zabbix; 503 si Zabbix no responde."""
    datos = cache.get(clave_cache)
    if datos is not None:
        return Response(datos)
    try:
        datos = funcion(ZabbixClient())
    except (ZabbixError, requests.RequestException) as error:
        return Response(
            {'detail': f'No fue posible consultar Zabbix: {error}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    cache.set(clave_cache, datos, CACHE_SEGUNDOS)
    return Response(datos)


class InfraestructuraEstadoView(APIView):
    """GET: estado del cluster MySQL + problemas activos."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        return _consultar(CACHE_ESTADO, lambda cliente: {
            'cluster': cliente.estado_cluster('Cluster'),
            'problemas': cliente.problemas(min_severidad=2),
        })


class InfraestructuraHostsView(APIView):
    """GET: servidores monitoreados y si su agente responde."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        return _consultar(CACHE_HOSTS, lambda cliente: cliente.hosts())


class InfraestructuraEventosHostView(APIView):
    """GET: historial de eventos técnicos de un servidor (RF-INF-03).

    Parámetro opcional ?dias=N (1 a 365, por defecto 30).
    """
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, hostid, format=None):
        try:
            dias = int(request.query_params.get('dias', 30))
        except ValueError:
            dias = 0
        if not 1 <= dias <= 365:
            return Response(
                {'detail': 'El parámetro dias debe ser un entero entre 1 y 365.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        desde = int(time.time()) - dias * 86400
        return _consultar(
            f'infraestructura:eventos:{hostid}:{dias}',
            lambda cliente: cliente.eventos_host(str(hostid), desde),
        )


class ActivosZabbixView(APIView):
    """GET: hosts de Cluster e Hypervisores con el formato de Activo del frontend."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        return _consultar(CACHE_ACTIVOS, self._consultar_activos)

    def _consultar_activos(self, cliente: ZabbixClient) -> list[dict[str, Any]]:
        grupos = cliente.obtener_grupos(['Cluster', 'Hypervisores'])
        groupids = [str(grupo['groupid']) for grupo in grupos]
        if not groupids:
            return []

        hosts = cliente.obtener_hosts(groupids)
        hostids = [str(host['hostid']) for host in hosts]
        items = cliente.obtener_items_mysql(hostids)
        problemas = cliente.obtener_problemas(hostids)

        problemas_por_host = self._problemas_por_host(cliente, problemas)
        items_por_host: dict[str, dict[str, dict[str, Any]]] = {}
        for item in items:
            items_por_host.setdefault(str(item['hostid']), {})[item['key_']] = item

        return [
            self._serializar_host(host, items_por_host, problemas_por_host)
            for host in hosts
        ]

    @staticmethod
    def _problemas_por_host(
        cliente: ZabbixClient,
        problemas: list[dict[str, Any]],
    ) -> Counter[str]:
        eventids = [str(problema['eventid']) for problema in problemas]
        eventos = cliente.obtener_eventos_con_hosts(eventids)
        host_por_evento = {
            str(evento['eventid']): str(evento['hosts'][0]['hostid'])
            for evento in eventos
            if evento.get('hosts')
        }
        return Counter(
            host_por_evento[str(problema['eventid'])]
            for problema in problemas
            if str(problema['eventid']) in host_por_evento
        )

    @staticmethod
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


class ZabbixWebhookView(APIView):
    """POST: Zabbix avisa a SICMA cuando se abre o se resuelve un problema."""
    authentication_classes = []
    permission_classes = []

    def post(self, request, format=None):
        secreto = getattr(settings, 'ZABBIX_WEBHOOK_SECRET', '')
        recibido = request.headers.get('X-Zabbix-Token', '')
        # Sin secreto configurado, compare_digest('', '') aceptaría cualquier POST.
        if not secreto:
            return Response(
                {'detail': 'La integración de webhook no está configurada.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not hmac.compare_digest(recibido, secreto):
            return Response(
                {'detail': 'Token de webhook no válido.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not isinstance(request.data, dict):
            return Response(
                {'detail': 'El cuerpo del webhook debe ser un objeto JSON.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EventoZabbixSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        # RF-INF-02: el evento queda registrado y abre o cierra su alerta.
        alerta = registrar_evento_zabbix(
            event_id=datos['event_id'],
            host=datos['host'],
            problema=datos['problem'],
            severidad=datos['severity'],
            estado=datos['status'],
        )
        cache.delete_many([CACHE_ESTADO, CACHE_ACTIVOS])  # el próximo GET trae datos frescos
        return Response(
            {
                'detail': 'Webhook recibido.',
                'alerta_id': alerta.id if alerta else None,
                'estado_alerta': alerta.estado if alerta else None,
            },
            status=status.HTTP_202_ACCEPTED,
        )
