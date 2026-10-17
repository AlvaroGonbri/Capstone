import logging
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Prefetch, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Medicion, Sensor, Ubicacion, UmbralAmbiental
from .serializers import (
    MedicionFilterSerializer,
    MedicionIngestSerializer,
    MedicionReadSerializer,
    SensorReadSerializer,
    UbicacionReadSerializer,
    UmbralFilterSerializer,
    UmbralReadSerializer,
    SensorWriteSerializer,
    UbicacionWriteSerializer,
    UmbralWriteSerializer,
)
from alertas.servicio import evaluar_medicion
from login.permissions import ADMIN_ROLES, READ_ROLES, RolePermission


logger = logging.getLogger(__name__)


class MedicionIngestView(APIView):
    permission_classes = [AllowAny]
    allowed_roles = READ_ROLES

    def get_authenticators(self):
        if self.request.method == 'POST':
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [RolePermission()]

    def get(self, request, format=None):
        filters = MedicionFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data

        queryset = Medicion.objects.all()
        if 'sensor' in values:
            queryset = queryset.filter(sensor_id=values['sensor'])
        if 'desde' in values:
            queryset = queryset.filter(fecha_hora_medicion__gte=values['desde'])
        if 'hasta' in values:
            queryset = queryset.filter(fecha_hora_medicion__lte=values['hasta'])
        if 'recibido_desde' in values:
            queryset = queryset.filter(fecha_hora_recepcion__gt=values['recibido_desde'])
        if 'origen' in values:
            queryset = queryset.filter(origen=values['origen'])

        paginator = MedicionPagination()
        page = paginator.paginate_queryset(
            queryset.order_by(values['ordering']),
            request,
            view=self,
        )
        serializer = MedicionReadSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, format=None):
        serializer = MedicionIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sensor_codigo = serializer.validated_data.pop('sensor_codigo')
        device_key = request.headers.get('X-Device-Key', '')
        sensor = Sensor.objects.filter(codigo=sensor_codigo).first()

        if sensor is None or sensor.estado != 'Activo' or not device_key:
            return Response(
                {'detail': 'Credenciales del dispositivo no válidas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not check_password(device_key, sensor.device_key_hash):
            return Response(
                {'detail': 'Credenciales del dispositivo no válidas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        with transaction.atomic():
            medicion, created = Medicion.objects.get_or_create(
                sensor=sensor,
                evento_id=str(serializer.validated_data['evento_id']),
                defaults={
                    **serializer.validated_data,
                    'fecha_hora_recepcion': timezone.now(),
                    'origen': 'Real',
                },
            )

        if created:
            # RF-AMB-04: la lectura queda guardada aunque la evaluación de alertas falle.
            try:
                evaluar_medicion(medicion)
            except Exception:
                logger.exception('No fue posible evaluar la medición %s contra los umbrales', medicion.id)

        return Response(
            {
                'id': medicion.id,
                'evento_id': medicion.evento_id,
                'duplicate': not created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SensorQuerysetMixin:
    def sensor_queryset(self):
        latest_measurement = Medicion.objects.order_by(
            '-fecha_hora_medicion',
            '-id',
        )
        return Sensor.objects.select_related('ubicacion').prefetch_related(
            Prefetch(
                'mediciones',
                queryset=latest_measurement[:1],
                to_attr='ultima_medicion_lista',
            )
        )


class LecturaPublicaEscrituraAdminMixin:
    """GET para todos los roles; escritura solo para administradores (matriz: catálogos)."""

    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return READ_ROLES if self.request.method == 'GET' else ADMIN_ROLES


def _nueva_clave_dispositivo(sensor):
    """Genera la device key: se guarda solo su hash y se muestra una única vez."""
    clave = secrets.token_urlsafe(24)
    sensor.device_key_hash = make_password(clave)
    return clave


class SensorListView(LecturaPublicaEscrituraAdminMixin, SensorQuerysetMixin, APIView):
    def get(self, request, format=None):
        sensors = self.sensor_queryset()
        return Response(SensorReadSerializer(sensors, many=True).data)

    def post(self, request, format=None):
        serializer = SensorWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sensor = Sensor(**serializer.validated_data)
        clave = _nueva_clave_dispositivo(sensor)
        sensor.save()
        datos = SensorReadSerializer(self.sensor_queryset().get(pk=sensor.pk)).data
        return Response({**datos, 'clave_dispositivo': clave}, status=status.HTTP_201_CREATED)


class SensorDetailView(LecturaPublicaEscrituraAdminMixin, SensorQuerysetMixin, APIView):
    def get(self, request, pk, format=None):
        sensor = get_object_or_404(self.sensor_queryset(), pk=pk)
        return Response(SensorReadSerializer(sensor).data)

    def patch(self, request, pk, format=None):
        sensor = get_object_or_404(Sensor, pk=pk)
        serializer = SensorWriteSerializer(sensor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SensorReadSerializer(self.sensor_queryset().get(pk=pk)).data)


class SensorClaveView(APIView):
    """POST: genera una device key nueva; la anterior deja de funcionar de inmediato."""
    permission_classes = [RolePermission]
    allowed_roles = ADMIN_ROLES

    def post(self, request, pk, format=None):
        sensor = get_object_or_404(Sensor, pk=pk)
        clave = _nueva_clave_dispositivo(sensor)
        sensor.save(update_fields=['device_key_hash'])
        return Response({'codigo': sensor.codigo, 'clave_dispositivo': clave})


class UbicacionListView(LecturaPublicaEscrituraAdminMixin, APIView):
    """GET: ubicaciones activas (?todas=1 incluye las desactivadas). POST: alta (administradores)."""

    def get(self, request, format=None):
        locations = Ubicacion.objects.order_by('sala', 'zona', 'rack', 'posicion')
        if request.query_params.get('todas') != '1':
            locations = locations.filter(activa=True)
        return Response(UbicacionReadSerializer(locations, many=True).data)

    def post(self, request, format=None):
        serializer = UbicacionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ubicacion = serializer.save()
        return Response(UbicacionReadSerializer(ubicacion).data, status=status.HTTP_201_CREATED)


class UbicacionDetailView(LecturaPublicaEscrituraAdminMixin, APIView):
    """PATCH: edita o desactiva (activa=false) una ubicación. Nunca se elimina (RN-02)."""

    def get(self, request, pk, format=None):
        return Response(UbicacionReadSerializer(get_object_or_404(Ubicacion, pk=pk)).data)

    def patch(self, request, pk, format=None):
        ubicacion = get_object_or_404(Ubicacion, pk=pk)
        serializer = UbicacionWriteSerializer(ubicacion, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(UbicacionReadSerializer(serializer.save()).data)


class UmbralListView(APIView):
    """GET: umbrales vigentes (de una ubicación con ?ubicacion=N, o de todas).

    POST: define un umbral nuevo; solo administradores (RF-AMB-03).
    """
    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return READ_ROLES if self.request.method == 'GET' else ADMIN_ROLES

    def get(self, request, format=None):
        filters = UmbralFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        latest_id = UmbralAmbiental.objects.filter(
            ubicacion_id=OuterRef('ubicacion_id'),
            variable=OuterRef('variable'),
        ).order_by('-version', '-vigente_desde', '-id').values('id')[:1]
        thresholds = UmbralAmbiental.objects.filter(id=Subquery(latest_id))
        if 'ubicacion' in filters.validated_data:
            thresholds = thresholds.filter(ubicacion_id=filters.validated_data['ubicacion'])
        thresholds = thresholds.order_by('ubicacion_id', 'variable')
        return Response(UmbralReadSerializer(thresholds, many=True).data)

    def post(self, request, format=None):
        serializer = UmbralWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        umbral = serializer.save()
        return Response(UmbralReadSerializer(umbral).data, status=status.HTTP_201_CREATED)


class MedicionPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500
