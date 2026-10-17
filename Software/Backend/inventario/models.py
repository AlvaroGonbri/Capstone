"""Inventario de activos (RF-ACT) y su catálogo de tipos (RF-CAT-03)."""
from django.conf import settings
from django.db import models


# Estados del ciclo de vida definidos en el enum de activo.estado (script SQL del equipo).
ESTADOS_ACTIVO = ('Operativo', 'Degradado', 'En_mantenimiento', 'Fuera_de_servicio', 'Retirado')
CRITICIDADES = ('Baja', 'Media', 'Alta', 'Critica')


class TipoActivo(models.Model):
    """Catálogo de tipos de activo. Lo crea SICMA (migración 0001), no el script SQL."""

    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'tipo_activo'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Activo(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    # Guarda el nombre del tipo; se valida contra el catálogo TipoActivo.
    tipo = models.CharField(max_length=100, null=True, blank=True)
    marca = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    numero_serie = models.CharField(max_length=150, unique=True)
    estado = models.CharField(max_length=17, default='Operativo')
    criticidad = models.CharField(max_length=7, default='Media')
    ubicacion = models.ForeignKey(
        'mediciones.Ubicacion',
        db_column='ubicacion_id',
        on_delete=models.DO_NOTHING,
        related_name='activos',
    )
    fecha_alta = models.DateTimeField()
    observaciones = models.TextField(null=True, blank=True)
    # Columna agregada por la migración 0001 de esta app (RF-ACT-04, RF-CAT-05).
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column='responsable_id',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='activos_a_cargo',
    )

    class Meta:
        managed = False
        db_table = 'activo'


class HistorialActivo(models.Model):
    """Registro de cambios de un activo (RF-ACT-03). Solo inserción."""

    id = models.BigAutoField(primary_key=True)
    activo = models.ForeignKey(Activo, db_column='activo_id', on_delete=models.DO_NOTHING, related_name='historial')
    campo_modificado = models.CharField(max_length=100)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column='usuario_id',
        on_delete=models.DO_NOTHING,
        related_name='+',
    )
    fecha_hora = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'historial_activo'
