from rest_framework import serializers

from .models import Medicion, Sensor, Ubicacion, UmbralAmbiental


class UbicacionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ubicacion
        fields = ('id', 'sala', 'zona', 'rack', 'posicion', 'ubicacion_padre_id')


class MedicionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicion
        fields = (
            'id',
            'sensor',
            'evento_id',
            'temperatura',
            'humedad',
            'fecha_hora_medicion',
            'fecha_hora_recepcion',
            'origen',
        )


class SensorReadSerializer(serializers.ModelSerializer):
    ubicacion = UbicacionReadSerializer(read_only=True)
    ultima_medicion = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = (
            'id',
            'codigo',
            'tipo',
            'estado',
            'intervalo_esperado_segundos',
            'ubicacion',
            'ultima_medicion',
        )

    def get_ultima_medicion(self, sensor):
        mediciones = getattr(sensor, 'ultima_medicion_lista', [])
        medicion = mediciones[0] if mediciones else None
        return MedicionReadSerializer(medicion).data if medicion else None


class UmbralReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UmbralAmbiental
        fields = (
            'variable',
            'valor_minimo',
            'valor_maximo',
            'version',
            'vigente_desde',
        )


class MedicionFilterSerializer(serializers.Serializer):
    sensor = serializers.IntegerField(required=False, min_value=1)
    desde = serializers.DateTimeField(required=False)
    hasta = serializers.DateTimeField(required=False)
    recibido_desde = serializers.DateTimeField(required=False)
    origen = serializers.ChoiceField(
        choices=('Real', 'Simulado'),
        required=False,
    )
    ordering = serializers.ChoiceField(
        choices=('fecha_hora_medicion', '-fecha_hora_medicion'),
        required=False,
        default='fecha_hora_medicion',
    )

    def validate(self, attrs):
        desde = attrs.get('desde')
        hasta = attrs.get('hasta')
        if desde and hasta and desde > hasta:
            raise serializers.ValidationError({
                'hasta': 'Debe ser posterior o igual a desde.',
            })
        return attrs


class UmbralFilterSerializer(serializers.Serializer):
    ubicacion = serializers.IntegerField(min_value=1)


class MedicionIngestSerializer(serializers.ModelSerializer):
    sensor_codigo = serializers.CharField(max_length=50, write_only=True)
    evento_id = serializers.UUIDField()

    class Meta:
        model = Medicion
        fields = (
            'sensor_codigo',
            'evento_id',
            'temperatura',
            'humedad',
            'fecha_hora_medicion',
        )

    def validate(self, attrs):
        temperatura = attrs.get('temperatura')
        humedad = attrs.get('humedad')

        if temperatura is None and humedad is None:
            raise serializers.ValidationError(
                'Debe enviar temperatura, humedad o ambas mediciones.'
            )

        if humedad is not None and not 0 <= humedad <= 100:
            raise serializers.ValidationError(
                {'humedad': 'Debe estar entre 0 y 100.'}
            )

        if temperatura is not None and not -40 <= temperatura <= 80:
            raise serializers.ValidationError(
                {'temperatura': 'Debe estar entre -40 y 80 grados Celsius.'}
            )

        return attrs
