from rest_framework import serializers

from .models import Alerta


class AlertaReadSerializer(serializers.ModelSerializer):
    sensor_codigo = serializers.CharField(source='sensor.codigo', default=None, read_only=True)
    ubicacion = serializers.IntegerField(source='sensor.ubicacion_id', default=None, read_only=True)
    evento_zabbix = serializers.CharField(
        source='host_problema_zabbix.identificador_externo', default=None, read_only=True,
    )
    # Servidor y problema por separado, para agrupar y contar las alertas por servidor (Panel).
    host = serializers.SerializerMethodField()
    problema = serializers.SerializerMethodField()
    ultima_gestion = serializers.SerializerMethodField()

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
            'host',
            'problema',
            'ultima_gestion',
        )

    @staticmethod
    def _partes(alerta):
        """Las alertas de Zabbix se guardan como 'host: problema' (alertas/zabbix.py).

        El nombre técnico de un host de Zabbix no admite ':', así que el primer ': ' los separa.
        """
        if alerta.origen == 'Zabbix':
            host, separador, problema = alerta.condicion.partition(': ')
            if separador and host:
                return host, problema
        return None, alerta.condicion

    def get_host(self, alerta):
        return self._partes(alerta)[0]

    def get_problema(self, alerta):
        return self._partes(alerta)[1]

    def get_ultima_gestion(self, alerta):
        g = next(iter(alerta.gestiones.all()), None)
        if g is None:
            return None
        nombre = (g.usuario.get_full_name() or g.usuario.get_username()) if g.usuario else None
        return {'accion': g.accion, 'usuario': nombre, 'comentario': g.comentario, 'fecha_hora': g.fecha_hora}


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


class GestionAlertaSerializer(serializers.Serializer):
    comentario = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
