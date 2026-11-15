from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from login.permissions import READ_ROLES, RolePermission
from mediciones.models import Ubicacion

from .agregacion import MAX_DIAS, Periodo, construir_reporte, zona_horaria
from .pdf import generar_pdf
from .resumen import resumen


class FiltroReporteSerializer(serializers.Serializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    zona = serializers.PrimaryKeyRelatedField(queryset=Ubicacion.objects.all(), required=False, allow_null=True)

    def validate(self, datos):
        hoy = timezone.now().astimezone(zona_horaria()).date()
        hasta = min(datos.get('hasta') or hoy, hoy)
        desde = datos.get('desde') or hasta - timedelta(days=29)
        if desde > hasta:
            raise serializers.ValidationError({'desde': 'La fecha inicial debe ser anterior o igual a la final.'})
        if (hasta - desde).days + 1 > MAX_DIAS:
            raise serializers.ValidationError({'desde': f'El período puede tener como máximo {MAX_DIAS} días.'})
        return Periodo(desde=desde, hasta=hasta, zona=datos.get('zona'))


def _periodo(request) -> Periodo:
    filtro = FiltroReporteSerializer(data=request.query_params)
    filtro.is_valid(raise_exception=True)
    return filtro.validated_data


class ResumenReporteView(APIView):
    """GET ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD&zona=<id>: KPIs, series, eventos y resumen del período.

    Sin fechas, los últimos 30 días (la app móvil no tiene filtro). Matriz de permisos, fila
    "Dashboards y reportes": consultan todos los roles menos Contratistas.
    """
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES
    throttle_scope = 'reportes'

    def get(self, request, format=None):
        reporte = construir_reporte(_periodo(request))
        reporte['resumen'] = resumen(reporte)
        return Response(reporte)


class PdfReporteView(APIView):
    """GET (mismos parámetros): el reporte en PDF, generado en el servidor."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES
    throttle_scope = 'reportes'

    def get(self, request, format=None):
        periodo = _periodo(request)
        reporte = construir_reporte(periodo)
        usuario = request.user.get_full_name() or request.user.get_username()
        contenido = generar_pdf(reporte, resumen(reporte), usuario)
        respuesta = HttpResponse(contenido, content_type='application/pdf')
        respuesta['Content-Disposition'] = f'attachment; filename="SICMA-reporte-{periodo.desde}_{periodo.hasta}.pdf"'
        return respuesta
