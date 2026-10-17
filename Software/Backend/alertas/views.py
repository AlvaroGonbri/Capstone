from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from login.permissions import ADMIN_ROLES, READ_ROLES, RolePermission
from mediciones.models import Ubicacion

from .models import ESTADOS_ABIERTOS, Alerta, ReglaAlerta
from .serializers import AlertaFilterSerializer, AlertaReadSerializer, ResponsablesSerializer
from .servicio import responsables_zona


class AlertaListView(APIView):
    """GET: alertas (por defecto solo las abiertas), de la más reciente a la más antigua."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        filtros = AlertaFilterSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        alertas = Alerta.objects.select_related('sensor', 'host_problema_zabbix')
        if filtros.validated_data['estado'] == 'abiertas':
            alertas = alertas.filter(estado__in=ESTADOS_ABIERTOS)
        if 'origen' in filtros.validated_data:
            alertas = alertas.filter(origen=filtros.validated_data['origen'])
        alertas = alertas.order_by('-fecha_apertura', '-id')[:100]
        return Response(AlertaReadSerializer(alertas, many=True).data)


class ResponsablesListView(APIView):
    """GET: responsables de alerta de cada zona."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        return Response([
            {'ubicacion': ubicacion_id, 'correos': responsables_zona(ubicacion_id)}
            for ubicacion_id in Ubicacion.objects.order_by('id').values_list('id', flat=True)
        ])


class ResponsablesZonaView(APIView):
    """PUT: reemplaza los responsables de alerta de una zona. Solo administradores."""
    permission_classes = [RolePermission]
    allowed_roles = ADMIN_ROLES

    def put(self, request, ubicacion_id, format=None):
        get_object_or_404(Ubicacion, pk=ubicacion_id)
        serializer = ResponsablesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correos = serializer.validated_data['correos']
        condicion = ReglaAlerta.condicion_zona(ubicacion_id)
        with transaction.atomic():
            reglas = ReglaAlerta.objects.select_for_update().filter(fuente='IoT', condicion=condicion)
            version = (reglas.aggregate(Max('version'))['version__max'] or 0) + 1
            regla = reglas.order_by('-version', '-id').first()
            if regla is None:
                regla = ReglaAlerta(fuente='IoT', condicion=condicion, severidad='Critica')
            regla.destinatarios = correos
            regla.version = version
            regla.save()
        return Response({'ubicacion': ubicacion_id, 'correos': correos})
