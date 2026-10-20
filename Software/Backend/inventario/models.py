"""Inventario de activos (RF-ACT) y sus catálogos de tipos y estados (RF-CAT-03)."""
from django.conf import settings
from django.db import models


# Estados que usa la lógica de SICMA: 'Operativo' es el estado de alta y 'Retirado' es la baja (RN-02).
# Se pueden cambiar su etiqueta y color, pero no renombrarlos ni desactivarlos.
ESTADO_INICIAL = 'Operativo'
ESTADO_RETIRADO = 'Retirado'
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


class EstadoActivo(models.Model):
    """Catálogo de estados de activo. Lo crea SICMA (migración 0002) con los valores del enum original."""

    nombre = models.CharField(max_length=50, unique=True)
    etiqueta = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default='medium')
    activo = models.BooleanField(default=True)
    es_sistema = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'estado_activo'
        ordering = ['orden', 'nombre']

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
    # Guarda el nombre del estado; se valida contra el catálogo EstadoActivo.
    estado = models.CharField(max_length=50, default=ESTADO_INICIAL)
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
