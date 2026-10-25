"""Intervenciones (RF-INT). Tablas del script SQL del equipo (managed=False), ampliadas por la migración 0001."""
from django.conf import settings
from django.db import models


# Ciclo de vida. 'Rechazada' la agrega la migración 0001 al enum original.
PENDIENTE = 'Pendiente'
APROBADA = 'Aprobada'
RECHAZADA = 'Rechazada'
EN_EJECUCION = 'EnEjecucion'
EJECUTADA = 'Ejecutada'
FALLIDA = 'Fallida'
CANCELADA = 'Cancelada'
ESTADOS_INTERVENCION = (PENDIENTE, 'CambiosSolicitados', APROBADA, RECHAZADA, EN_EJECUCION, EJECUTADA, FALLIDA, CANCELADA)
ESTADOS_CERRADOS = (RECHAZADA, EJECUTADA, FALLIDA, CANCELADA)


class Intervencion(models.Model):
    id = models.BigAutoField(primary_key=True)
    objetivo = models.CharField(max_length=500)
    descripcion = models.TextField(null=True, blank=True)
    impacto_esperado = models.TextField(null=True, blank=True)  # servicios afectados (Forms)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_termino = models.DateTimeField(null=True, blank=True)
    # Técnico asignado por el Administrador (RF-INT-05). Nulo hasta la asignación.
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column='responsable_id',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='intervenciones_asignadas',
    )
    plan_reversa = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=18, default=PENDIENTE)
    # Columnas agregadas por la migración 0001 (datos que llegan desde Microsoft Forms).
    solicitante_nombre = models.CharField(max_length=200, null=True, blank=True)
    solicitante_correo = models.CharField(max_length=254, null=True, blank=True)
    rack = models.CharField(max_length=200, null=True, blank=True)
    # Id de la respuesta de Forms: relaciona los correos del flujo con la intervención.
    origen_externo_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    fecha_solicitud = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    observacion_cierre = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'intervencion'


class DecisionIntervencion(models.Model):
    """Aprobación o rechazo de la Jefatura en Teams (RF-INT-03). Solo inserción."""

    id = models.BigAutoField(primary_key=True)
    intervencion = models.ForeignKey(
        Intervencion, db_column='intervencion_id', on_delete=models.DO_NOTHING, related_name='decisiones',
    )
    # Usuario de SICMA con el correo del decisor, si existe (columna nula desde la migración 0001).
    decisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column='decisor_id', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
    )
    decisor_correo = models.CharField(max_length=254, null=True, blank=True)
    decision = models.CharField(max_length=18)  # Aprobada | Rechazada
    observacion = models.TextField(null=True, blank=True)
    fecha_hora = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'decision_intervencion'


class IntervencionActivo(models.Model):
    """Activos afectados por una intervención (los elige el Administrador al asignarla)."""

    id = models.BigAutoField(primary_key=True)
    intervencion = models.ForeignKey(
        Intervencion, db_column='intervencion_id', on_delete=models.DO_NOTHING, related_name='activos_afectados',
    )
    activo = models.ForeignKey(
        'inventario.Activo', db_column='activo_id', on_delete=models.DO_NOTHING, related_name='intervenciones',
    )
    estado_final_activo = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'intervencion_activo'
        unique_together = ('intervencion', 'activo')


class IntervencionPersona(models.Model):
    """Personal externo que trabajará en la intervención. Lo elige el Administrador al asignarla."""

    # db_constraint=False: intervencion.id y persona_autorizada.id son BIGINT UNSIGNED (script del equipo).
    intervencion = models.ForeignKey(
        Intervencion, on_delete=models.CASCADE, db_constraint=False, related_name='personal_externo',
    )
    persona = models.ForeignKey(
        'accesos.PersonaAutorizada', on_delete=models.CASCADE, db_constraint=False, related_name='intervenciones',
    )
    agregada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField()
    # Al iniciar, cada persona demuestra con su huella que es quien fue asignada.
    verificada_en = models.DateTimeField(null=True, blank=True)
    verificada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    # Permisos de acceso que SICMA creó para la ventana de la intervención (se revocan al quitarla o cerrar).
    permisos = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'intervencion_persona'
        unique_together = ('intervencion', 'persona')
        ordering = ['id']
