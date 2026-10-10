from django.db import models


class Sensor(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=50, unique=True)
    tipo = models.CharField(max_length=100)
    ubicacion = models.ForeignKey(
        'Ubicacion',
        db_column='ubicacion_id',
        on_delete=models.DO_NOTHING,
        related_name='sensores',
    )
    estado = models.CharField(max_length=8)
    intervalo_esperado_segundos = models.PositiveIntegerField()
    device_key_hash = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'sensor'


class Medicion(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey(
        Sensor,
        db_column='sensor_id',
        on_delete=models.DO_NOTHING,
        related_name='mediciones',
    )
    evento_id = models.CharField(max_length=36)
    temperatura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    humedad = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fecha_hora_medicion = models.DateTimeField()
    fecha_hora_recepcion = models.DateTimeField()
    origen = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'medicion'
        unique_together = ('sensor', 'evento_id')


class Ubicacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    sala = models.CharField(max_length=100)
    zona = models.CharField(max_length=100, null=True, blank=True)
    rack = models.CharField(max_length=100, null=True, blank=True)
    posicion = models.CharField(max_length=100, null=True, blank=True)
    ubicacion_padre = models.ForeignKey(
        'self',
        db_column='ubicacion_padre_id',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ubicaciones_hijas',
    )

    class Meta:
        managed = False
        db_table = 'ubicacion'


class UmbralAmbiental(models.Model):
    id = models.BigAutoField(primary_key=True)
    ubicacion = models.ForeignKey(
        Ubicacion,
        db_column='ubicacion_id',
        on_delete=models.DO_NOTHING,
        related_name='umbrales',
    )
    variable = models.CharField(max_length=11)
    valor_minimo = models.DecimalField(max_digits=6, decimal_places=2)
    valor_maximo = models.DecimalField(max_digits=6, decimal_places=2)
    version = models.PositiveIntegerField()
    vigente_desde = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'umbral_ambiental'
