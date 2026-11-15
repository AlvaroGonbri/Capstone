import logging

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from login.permissions import ADMIN_ROLES, PRIVILEGIADO, RolePermission, es_privilegiado

from .avisos import avisar_renovacion
from .estado import estado_general
from .pruebas import PRUEBAS, probar
from .secretos import SECRETOS, renovar


logger = logging.getLogger(__name__)


def desde_tunel(request) -> bool:
    """Lo que llega por Cloudflare trae CF-Connecting-IP y CF-Ray (Cloudflare los pone siempre).

    En la red local alguien podría agregarlas a mano, pero solo conseguiría que SICMA lo trate
    como si viniera de internet (más restricciones, no menos).
    """
    return bool(request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('HTTP_CF_RAY'))


class EstadoIntegracionesView(APIView):
    """GET: estado de Zabbix, webhook, correo, buzón, túnel, procesos, sensores y lectores."""
    permission_classes = [RolePermission]
    allowed_roles = ADMIN_ROLES

    def get(self, request, format=None):
        return Response(estado_general(
            red_local=not desde_tunel(request),
            puede_renovar=es_privilegiado(request.user),
        ))


class ProbarIntegracionView(APIView):
    """POST: comprueba en vivo una integración (zabbix | correo | tunel)."""
    permission_classes = [RolePermission]
    allowed_roles = ADMIN_ROLES
    throttle_scope = 'integraciones_prueba'

    def post(self, request, nombre, format=None):
        if nombre not in PRUEBAS:
            return Response({'detail': 'Integración desconocida.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(probar(nombre))


class RenovacionSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False)
    inmediato = serializers.BooleanField(required=False, default=False)


class RenovarSecretoView(APIView):
    """POST: genera un secreto nuevo y lo devuelve una sola vez.

    Solo el Administrador Privilegiado, reingresando su contraseña y desde la red local: la ruta
    está bajo /api/integraciones/, que el túnel de Cloudflare no publica, y además se rechaza
    aquí todo lo que llegue a través de Cloudflare.
    """
    permission_classes = [RolePermission]
    allowed_roles = (PRIVILEGIADO,)
    throttle_scope = 'integraciones_renovacion'

    def post(self, request, nombre, format=None):
        if nombre not in SECRETOS:
            return Response({'detail': 'Secreto desconocido.'}, status=status.HTTP_404_NOT_FOUND)
        if desde_tunel(request):
            return Response(
                {'detail': 'La renovación solo está disponible desde la red local, no a través de internet.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        datos = RenovacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        ip = request.META.get('REMOTE_ADDR', '')
        if not request.user.check_password(datos.validated_data['password']):
            logger.warning('Renovación de %s rechazada: contraseña incorrecta (usuario %s, IP %s).',
                           nombre, request.user.get_username(), ip)
            return Response({'detail': 'La contraseña no es correcta.'}, status=status.HTTP_400_BAD_REQUEST)

        inmediato = datos.validated_data['inmediato']
        valor, fila = renovar(nombre, request.user, ip, inmediato=inmediato)
        logger.info('%s renovó %s desde %s (inmediato=%s).', request.user.get_username(), nombre, ip, inmediato)
        avisar_renovacion(nombre, request.user, ip, fila, inmediato)

        respuesta = Response({
            'nombre': nombre,
            'secreto': valor,
            'renovado_en': fila.renovado_en,
            'anterior_valido_hasta': fila.anterior_valido_hasta,
        })
        respuesta['Cache-Control'] = 'no-store'
        return respuesta
