from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.db.models import Prefetch, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
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
)


class MedicionIngestView(APIView):
    permission_classes = [AllowAny]

    def get_authenticators(self):
        if self.request.method == 'POST':
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsAuthenticated()]

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
        sensor = get_object_or_404(Sensor, codigo=sensor_codigo)

        if sensor.estado != 'Activo' or not device_key:
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


class SensorListView(SensorQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        sensors = self.sensor_queryset()
        return Response(SensorReadSerializer(sensors, many=True).data)


class SensorDetailView(SensorQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, format=None):
        sensor = get_object_or_404(self.sensor_queryset(), pk=pk)
        return Response(SensorReadSerializer(sensor).data)


class UbicacionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        locations = Ubicacion.objects.order_by('sala', 'zona', 'rack', 'posicion')
        return Response(UbicacionReadSerializer(locations, many=True).data)


class UmbralListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        filters = UmbralFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        location_id = filters.validated_data['ubicacion']
        latest_id = UmbralAmbiental.objects.filter(
            ubicacion_id=location_id,
            variable=OuterRef('variable'),
        ).order_by('-version', '-vigente_desde', '-id').values('id')[:1]
        thresholds = UmbralAmbiental.objects.filter(
            id=Subquery(latest_id),
        ).order_by('variable')
        return Response(UmbralReadSerializer(thresholds, many=True).data)


class MedicionPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500
