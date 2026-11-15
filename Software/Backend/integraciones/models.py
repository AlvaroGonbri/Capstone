"""Estado de las integraciones y secretos que SICMA genera (vista Integraciones)."""
from django.db import models


class SecretoIntegracion(models.Model):
    """Secreto compartido que SICMA genera y solo verifica: se guarda su hash, nunca el valor.

    Mientras no exista la fila vale el del .env (ZABBIX_WEBHOOK_SECRET / INTERVENCIONES_TOKEN).
    Tras renovar, el anterior sigue sirviendo hasta `anterior_valido_hasta` (período de gracia).
    """

    nombre = models.CharField(max_length=40, unique=True)
    hash_actual = models.CharField(max_length=64)
    hash_anterior = models.CharField(max_length=64, blank=True, default='')
    anterior_valido_hasta = models.DateTimeField(null=True, blank=True)
    renovado_en = models.DateTimeField()
    renovado_por = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        db_table = 'secreto_integracion'


class RenovacionSecreto(models.Model):
    """Auditoría de las renovaciones: quién, cuándo y desde qué IP (nunca el valor)."""

    secreto = models.CharField(max_length=40)
    usuario_id = models.IntegerField(null=True, blank=True)
    nombre_usuario = models.CharField(max_length=150, blank=True, default='')
    fecha = models.DateTimeField()
    ip = models.CharField(max_length=45, blank=True, default='')
    # True si la clave anterior se anuló de inmediato, sin período de gracia (p. ej. por filtración).
    inmediato = models.BooleanField(default=False)

    class Meta:
        db_table = 'renovacion_secreto'
        ordering = ['-fecha', '-id']


class ActividadIntegracion(models.Model):
    """Última señal de cada integración: latidos de los procesos periódicos, avisos del webhook
    de Zabbix, correos del flujo de Power Automate y contacto de los agentes del lector."""

    clave = models.CharField(max_length=60, unique=True)
    ultima_actividad = models.DateTimeField(null=True, blank=True)
    ultimo_exito = models.DateTimeField(null=True, blank=True)
    ultimo_error = models.TextField(blank=True, default='')
    fecha_error = models.DateTimeField(null=True, blank=True)
    # Cada cuánto debería dar señales (procesos periódicos); None = el valor por defecto.
    intervalo_segundos = models.PositiveIntegerField(null=True, blank=True)
    rechazos = models.PositiveIntegerField(default=0)
    ultimo_rechazo = models.DateTimeField(null=True, blank=True)
    detalle_rechazo = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        db_table = 'actividad_integracion'
