from rest_framework import serializers

from .models import Alerta


class AlertaReadSerializer(serializers.ModelSerializer):
    sensor_codigo = serializers.CharField(source='sensor.codigo', default=None, read_only=True)
    ubicacion = serializers.IntegerField(source='sensor.ubicacion_id', default=None, read_only=True)
    evento_zabbix = serializers.CharField(
        source='host_problema_zabbix.identificador_externo', default=None, read_only=True,
    )

    class Meta:
        model = Alerta
        fields = (
            'id',
            'origen',
            'condicion',
            'severidad',
            'estado',
            'fecha_apertura',
            'contador_ocurrencias',
            'fecha_ultima_ocurrencia',
            'sensor_codigo',
            'ubicacion',
            'evento_zabbix',
        )


class AlertaFilterSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=('abiertas', 'todas'), default='abiertas')
    origen = serializers.ChoiceField(choices=('IoT', 'Biometria', 'Zabbix'), required=False)


class ResponsablesSerializer(serializers.Serializer):
    """Correos que reciben las alertas de una zona (RF-CAT-05)."""

    correos = serializers.ListField(
        child=serializers.EmailField(max_length=254),
        allow_empty=True,
        max_length=20,
    )

    def validate_correos(self, correos):
        # Sin duplicados, conservando el orden.
        return list(dict.fromkeys(correo.strip().lower() for correo in correos))
