"""Tablas de alertas del script SQL del equipo (managed=False: Django no las crea ni altera)."""
from django.db import models


ESTADOS_ABIERTOS = ('Nueva', 'Reconocida')


class Alerta(models.Model):
    id = models.BigAutoField(primary_key=True)
    origen = models.CharField(max_length=9)  # IoT | Biometria | Zabbix
    condicion = models.CharField(max_length=500)
    severidad = models.CharField(max_length=11)  # Informativa | Advertencia | Alta | Critica
    estado = models.CharField(max_length=10, default='Nueva')  # Nueva | Reconocida | Cerrada
    fecha_apertura = models.DateTimeField()
    contador_ocurrencias = models.PositiveIntegerField(default=1)
    fecha_ultima_ocurrencia = models.DateTimeField(null=True, blank=True)
    sensor = models.ForeignKey(
        'mediciones.Sensor',
        db_column='sensor_id',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='alertas',
    )
    host_problema_zabbix = models.ForeignKey(
        'HostProblemaZabbix',
        db_column='host_problema_zabbix_id',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='alertas',
    )
    punto_acceso_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'alerta'


class HostProblemaZabbix(models.Model):
    """Problema recibido desde Zabbix (RF-INF-02). identificador_externo = event_id de Zabbix."""

    id = models.BigAutoField(primary_key=True)
    identificador_externo = models.CharField(max_length=255, unique=True)
    activo_id = models.BigIntegerField(null=True, blank=True)
    disponibilidad = models.CharField(max_length=50, null=True, blank=True)
    severidad = models.CharField(max_length=50, null=True, blank=True)
    estado = models.CharField(max_length=50, null=True, blank=True)  # PROBLEM | RESOLVED
    fecha_ultima_sincronizacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'host_problema_zabbix'


class Notificacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    alerta = models.ForeignKey(
        Alerta,
        db_column='alerta_id',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='notificaciones',
    )
    intervencion_id = models.BigIntegerField(null=True, blank=True)
    canal = models.CharField(max_length=13)  # SMTP | PowerAutomate
    destinatario = models.CharField(max_length=255)
    fecha_envio = models.DateTimeField()
    resultado = models.CharField(max_length=7)  # Enviado | Fallido

    class Meta:
        managed = False
        db_table = 'notificacion'


class ReglaAlerta(models.Model):
    """Enrutamiento de alertas. Para el ambiente hay una regla por zona:
    fuente='IoT', condicion='ubicacion:<id>' y destinatarios = lista de correos (RF-CAT-05)."""

    id = models.BigAutoField(primary_key=True)
    fuente = models.CharField(max_length=100)
    condicion = models.CharField(max_length=500)
    severidad = models.CharField(max_length=11)
    destinatarios = models.JSONField(null=True, blank=True)
    horario_notificacion = models.CharField(max_length=255, null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'regla_alerta'

    @staticmethod
    def condicion_zona(ubicacion_id):
        return f'ubicacion:{ubicacion_id}'


class GestionAlerta(models.Model):
    """Quién reconoció o cerró una alerta a mano, cuándo y con qué comentario (trazabilidad)."""

    RECONOCER = 'Reconocida'
    CERRAR = 'Cerrada'

    # db_constraint=False: alerta.id es BIGINT UNSIGNED (script del equipo).
    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE, db_constraint=False, related_name='gestiones')
    accion = models.CharField(max_length=10)
    comentario = models.CharField(max_length=255, blank=True, default='')
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_hora = models.DateTimeField()

    class Meta:
        db_table = 'gestion_alerta'
        ordering = ['-fecha_hora', '-id']
