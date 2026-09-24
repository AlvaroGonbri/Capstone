from django.db import models


class Sensor(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=50, unique=True)
    tipo = models.CharField(max_length=100)
    ubicacion_id = models.BigIntegerField()
    estado = models.CharField(max_length=8)
    intervalo_esperado_segundos = models.PositiveIntegerField()
    device_key_hash = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'sensor'


class Medicion(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey(Sensor, db_column='sensor_id', on_delete=models.DO_NOTHING)
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
