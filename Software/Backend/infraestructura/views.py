from collections.abc import Callable
import hmac
import time
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

import requests

from alertas.zabbix import registrar_evento_zabbix
from login.permissions import READ_ROLES, RolePermission

from .models import EstadoInfraestructura
from .serializers import EventoZabbixSerializer
from .sincronizacion import (
    ANTIGUEDAD_MAXIMA,
    INTERVALO_SEGUNDOS,
    consultar_activos,
    consultar_estado,
    foto_vigente,
    marcar_webhook,
)
from .zabbix_client import ZabbixClient, ZabbixError


CACHE_SEGUNDOS = 30  # evita consultar Zabbix en cada request del frontend
CACHE_ACTIVOS = 'infraestructura:activos'
CACHE_ESTADO = 'infraestructura:estado'
CACHE_HOSTS = 'infraestructura:hosts'


def _consultar(clave_cache: str, funcion: Callable[[ZabbixClient], Any], foto: str | None = None) -> Response:
    """Devuelve la foto de la sincronización periódica, los datos en caché o consulta Zabbix.

    503 si hay que consultar Zabbix y no responde.
    """
    if foto:
        datos = foto_vigente(foto)
        if datos is not None:
            return Response(datos)
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
        return _consultar(CACHE_ESTADO, consultar_estado, foto='estado')


class InfraestructuraHostsView(APIView):
    """GET: servidores monitoreados y si su agente responde."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        return _consultar(CACHE_HOSTS, lambda cliente: cliente.hosts(), foto='hosts')


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
        return _consultar(CACHE_ACTIVOS, lambda cliente: consultar_activos(cliente)[0], foto='activos')


class SincronizacionView(APIView):
    """GET: resultado de la última consulta periódica a Zabbix (RF-INF-01)."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        foto = EstadoInfraestructura.objects.filter(pk=1).first()
        ultima = foto.ultima_exitosa if foto else None
        return Response({
            'intervalo_segundos': INTERVALO_SEGUNDOS,
            'ultimo_intento': foto.ultimo_intento if foto else None,
            'ultima_exitosa': ultima,
            'al_dia': bool(ultima) and timezone.now() - ultima <= ANTIGUEDAD_MAXIMA,
            'error': (foto.error or None) if foto else None,
        })


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
        # El próximo GET trae datos frescos: se descarta la caché y la foto periódica queda vieja.
        cache.delete_many([CACHE_ESTADO, CACHE_ACTIVOS, CACHE_HOSTS])
        marcar_webhook()
        return Response(
            {
                'detail': 'Webhook recibido.',
                'alerta_id': alerta.id if alerta else None,
                'estado_alerta': alerta.estado if alerta else None,
            },
            status=status.HTTP_202_ACCEPTED,
        )
