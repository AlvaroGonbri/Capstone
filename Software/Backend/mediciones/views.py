import logging
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Prefetch, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Medicion, Sensor, Ubicacion, UmbralAmbiental
from .serializers import (
    HistorialSensorFilterSerializer,
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


# Período del gráfico -> (duración, largo de cada tramo en segundos). Unos 150 a 180 puntos por serie.
RANGOS_HISTORIAL = {
    '24h': (timedelta(hours=24), 10 * 60),
    '7d': (timedelta(days=7), 60 * 60),
    '30d': (timedelta(days=30), 4 * 60 * 60),
}

_fecha_iso = serializers.DateTimeField().to_representation


def _resumen_tramo(valores):
    """Promedio, mínimo y máximo de un tramo; None si no hubo lecturas de esa variable."""
    if not valores:
        return None, None, None
    return round(sum(valores) / len(valores), 2), min(valores), max(valores)


def _umbrales_vigentes(ubicacion_id):
    umbrales = {}
    for variable in ('Temperatura', 'Humedad'):
        vigente = (
            UmbralAmbiental.objects.filter(ubicacion_id=ubicacion_id, variable=variable)
            .order_by('-version', '-vigente_desde', '-id')
            .first()
        )
        umbrales[variable.lower()] = (
            {'minimo': float(vigente.valor_minimo), 'maximo': float(vigente.valor_maximo)} if vigente else None
        )
    return umbrales


class SensorHistorialView(APIView):
    """GET ?rango=24h|7d|30d: lecturas de un sensor promediadas por tramo, para el gráfico de
    temperatura y humedad (RF-AMB). Cada punto trae promedio, mínimo y máximo del tramo.

    Los tramos sin lecturas no se envían: el gráfico los muestra como "sin datos" en vez de
    unir los puntos de antes y después. Va bajo /api/sensores/ porque el túnel publica
    /api/ pero bloquea /api/mediciones/ (ingreso de lecturas de los dispositivos)."""

    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, pk, format=None):
        filtros = HistorialSensorFilterSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        rango = filtros.validated_data['rango']
        duracion, paso = RANGOS_HISTORIAL[rango]
        sensor = get_object_or_404(Sensor.objects.select_related('ubicacion'), pk=pk)

        hasta = timezone.now()
        # El inicio se alinea al tramo, así cada punto representa un tramo completo.
        inicio = int((hasta - duracion).timestamp()) // paso * paso
        desde = datetime.fromtimestamp(inicio, tz=dt_timezone.utc)

        tramos = {}
        lecturas = (
            Medicion.objects.filter(sensor=sensor, fecha_hora_medicion__gte=desde, fecha_hora_medicion__lte=hasta)
            .order_by('fecha_hora_medicion')
            .values_list('fecha_hora_medicion', 'temperatura', 'humedad')
        )
        for fecha, temperatura, humedad in lecturas.iterator():
            clave = int(fecha.timestamp()) // paso * paso
            tramo = tramos.setdefault(clave, {'lecturas': 0, 'temperatura': [], 'humedad': []})
            tramo['lecturas'] += 1
            if temperatura is not None:
                tramo['temperatura'].append(float(temperatura))
            if humedad is not None:
                tramo['humedad'].append(float(humedad))

        puntos = []
        for clave in sorted(tramos):
            tramo = tramos[clave]
            temperatura, temperatura_min, temperatura_max = _resumen_tramo(tramo['temperatura'])
            humedad, humedad_min, humedad_max = _resumen_tramo(tramo['humedad'])
            puntos.append({
                'fecha': _fecha_iso(datetime.fromtimestamp(clave, tz=dt_timezone.utc)),
                'lecturas': tramo['lecturas'],
                'temperatura': temperatura,
                'temperatura_min': temperatura_min,
                'temperatura_max': temperatura_max,
                'humedad': humedad,
                'humedad_min': humedad_min,
                'humedad_max': humedad_max,
            })

        ubicacion = sensor.ubicacion
        return Response({
            'sensor': {
                'id': sensor.id,
                'codigo': sensor.codigo,
                'ubicacion': ' · '.join(filter(None, (ubicacion.sala, ubicacion.zona, ubicacion.rack))),
            },
            'rango': rango,
            'desde': _fecha_iso(desde),
            'hasta': _fecha_iso(hasta),
            'paso_segundos': paso,
            'umbrales': _umbrales_vigentes(ubicacion.id),
            'puntos': puntos,
        })


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
    Con ?ubicacion=N&historial=1, todas las versiones de esa zona (la más reciente primero).

    POST: define un umbral nuevo; solo administradores (RF-AMB-03).
    """
    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return READ_ROLES if self.request.method == 'GET' else ADMIN_ROLES

    def get(self, request, format=None):
        filters = UmbralFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        if filters.validated_data['historial']:
            versiones = UmbralAmbiental.objects.filter(
                ubicacion_id=filters.validated_data['ubicacion'],
            ).order_by('-vigente_desde', '-id')
            return Response(UmbralReadSerializer(versiones, many=True).data)
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
