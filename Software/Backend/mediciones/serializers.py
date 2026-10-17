from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from .models import Medicion, Sensor, Ubicacion, UmbralAmbiental


class UbicacionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ubicacion
        fields = ('id', 'sala', 'zona', 'rack', 'posicion', 'ubicacion_padre_id', 'activa')


class UbicacionWriteSerializer(serializers.ModelSerializer):
    """Alta y edición de ubicaciones y zonas (RF-CAT-01, RF-CAT-04). Desactivar = activa=False."""

    ubicacion_padre = serializers.PrimaryKeyRelatedField(
        queryset=Ubicacion.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Ubicacion
        fields = ('sala', 'zona', 'rack', 'posicion', 'ubicacion_padre', 'activa')

    def validate_ubicacion_padre(self, padre):
        if padre is None:
            return padre
        if self.instance and padre.pk == self.instance.pk:
            raise serializers.ValidationError('Una ubicación no puede ser su propio padre.')
        if not padre.activa:
            raise serializers.ValidationError('La ubicación padre está desactivada.')
        return padre

    def validate(self, attrs):
        if self.instance and self.instance.activa and attrs.get('activa') is False:
            # RN-02: no se deja huérfano lo que sigue en uso.
            from inventario.models import Activo

            ubicacion = self.instance
            en_uso = []
            if ubicacion.sensores.filter(estado='Activo').exists():
                en_uso.append('sensores activos')
            if Activo.objects.filter(ubicacion=ubicacion).exclude(estado='Retirado').exists():
                en_uso.append('activos sin retirar')
            if ubicacion.ubicaciones_hijas.filter(activa=True).exists():
                en_uso.append('ubicaciones hijas activas')
            if en_uso:
                raise serializers.ValidationError(
                    {'activa': f'No se puede desactivar: tiene {", ".join(en_uso)}.'}
                )
        return attrs


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


class SensorWriteSerializer(serializers.ModelSerializer):
    """Alta y edición de dispositivos IoT (RF-CAT-02). Desactivar = estado 'Inactivo'.

    El código no se cambia después del alta: el dispositivo se identifica con él (RN-01).
    """

    ubicacion = serializers.PrimaryKeyRelatedField(queryset=Ubicacion.objects.all())
    estado = serializers.ChoiceField(choices=('Activo', 'Inactivo'), required=False)
    intervalo_esperado_segundos = serializers.IntegerField(min_value=1, max_value=86400)

    class Meta:
        model = Sensor
        fields = ('codigo', 'tipo', 'ubicacion', 'estado', 'intervalo_esperado_segundos')

    def validate_codigo(self, codigo):
        if self.instance and codigo != self.instance.codigo:
            raise serializers.ValidationError('El código de un dispositivo no se puede cambiar.')
        return codigo

    def validate_ubicacion(self, ubicacion):
        if not ubicacion.activa:
            raise serializers.ValidationError('La ubicación está desactivada.')
        return ubicacion


class UmbralReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UmbralAmbiental
        fields = (
            'id',
            'ubicacion',
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
    ubicacion = serializers.IntegerField(min_value=1, required=False)


class UmbralWriteSerializer(serializers.ModelSerializer):
    """Define un umbral nuevo (RF-AMB-03). Nunca edita: crea la versión siguiente."""

    # Rango de medición del DHT22 para temperatura; la humedad es porcentual.
    LIMITES = {'Temperatura': (-40, 80), 'Humedad': (0, 100)}

    ubicacion = serializers.PrimaryKeyRelatedField(queryset=Ubicacion.objects.all())
    variable = serializers.ChoiceField(choices=tuple(LIMITES))

    class Meta:
        model = UmbralAmbiental
        fields = ('ubicacion', 'variable', 'valor_minimo', 'valor_maximo')

    def validate(self, attrs):
        minimo, maximo = attrs['valor_minimo'], attrs['valor_maximo']
        if minimo >= maximo:
            raise serializers.ValidationError(
                {'valor_maximo': 'El valor máximo debe ser mayor que el mínimo.'}
            )
        piso, techo = self.LIMITES[attrs['variable']]
        if minimo < piso or maximo > techo:
            raise serializers.ValidationError(
                {'detail': f'Para {attrs["variable"]} los valores deben estar entre {piso} y {techo}.'}
            )
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            ultima = (
                UmbralAmbiental.objects.select_for_update()
                .filter(ubicacion=validated_data['ubicacion'], variable=validated_data['variable'])
                .aggregate(Max('version'))['version__max']
            )
            return UmbralAmbiental.objects.create(
                **validated_data,
                version=(ultima or 0) + 1,
                vigente_desde=timezone.now(),
            )


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
