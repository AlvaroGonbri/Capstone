from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .models import Medicion, Sensor
from .serializers import MedicionIngestSerializer


class MedicionIngestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

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
