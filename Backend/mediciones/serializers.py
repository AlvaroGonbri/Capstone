from rest_framework import serializers

from .models import Medicion


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

        return attrs
