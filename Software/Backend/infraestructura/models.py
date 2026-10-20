"""Última foto de Zabbix tomada por la sincronización periódica (RF-INF-01)."""
from django.db import models


class EstadoInfraestructura(models.Model):
    """Una sola fila (id=1). La escribe `manage.py sincronizar_zabbix` y la leen las vistas,
    así el estado se consulta a Zabbix cada minuto aunque nadie tenga abierto el frontend."""

    ultimo_intento = models.DateTimeField(null=True, blank=True)
    ultima_exitosa = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    activos = models.JSONField(null=True, blank=True)
    estado = models.JSONField(null=True, blank=True)
    hosts = models.JSONField(null=True, blank=True)
    # Un webhook posterior a la foto la deja vieja: la vista vuelve a consultar en directo.
    ultimo_webhook = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'estado_infraestructura'
        verbose_name = 'estado de infraestructura'

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]
