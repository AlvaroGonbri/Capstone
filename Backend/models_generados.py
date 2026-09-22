# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Activo(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(unique=True, max_length=50)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=100, blank=True, null=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    numero_serie = models.CharField(unique=True, max_length=150)
    estado = models.CharField(max_length=17)
    criticidad = models.CharField(max_length=7)
    ubicacion = models.ForeignKey('Ubicacion', models.DO_NOTHING)
    fecha_alta = models.DateTimeField(db_comment='UTC (RNF-INT-02)')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'activo'
        db_table_comment = 'Activos gestionados (inventario técnico).'


class Alerta(models.Model):
    id = models.BigAutoField(primary_key=True)
    origen = models.CharField(max_length=9)
    condicion = models.CharField(max_length=500)
    severidad = models.CharField(max_length=11)
    estado = models.CharField(max_length=10)
    fecha_apertura = models.DateTimeField(db_comment='UTC (RNF-INT-02)')
    contador_ocurrencias = models.PositiveIntegerField()
    fecha_ultima_ocurrencia = models.DateTimeField(blank=True, null=True, db_comment='UTC (RNF-INT-02)')
    sensor = models.ForeignKey('Sensor', models.DB_SET_NULL, blank=True, null=True)
    host_problema_zabbix = models.ForeignKey('HostProblemaZabbix', models.DB_SET_NULL, blank=True, null=True)
    punto_acceso = models.ForeignKey('PuntoAcceso', models.DB_SET_NULL, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'alerta'
        db_table_comment = 'Alertas generadas por IoT, Biometria o Zabbix. FKs opcionales SET NULL segun origen.'


class ArchivoAdjunto(models.Model):
    id = models.BigAutoField(primary_key=True)
    activo = models.ForeignKey(Activo, models.DO_NOTHING)
    nombre_archivo = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=3)
    tamano_bytes = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(db_comment='UTC (RNF-INT-02)')
    usuario = models.ForeignKey('Usuario', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'archivo_adjunto'
        db_table_comment = 'Archivos adjuntos asociados a un activo.'


class BitacoraActivo(models.Model):
    id = models.BigAutoField(primary_key=True)
    entrada_bitacora = models.ForeignKey('EntradaBitacora', models.DO_NOTHING)
    activo = models.ForeignKey(Activo, models.DO_NOTHING)
    accion = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'bitacora_activo'
        db_table_comment = 'Detalle de activos referenciados en una entrada de bitacora.'


class ConfiguracionIntegracionZabbix(models.Model):
    id = models.BigAutoField(primary_key=True)
    url = models.CharField(max_length=500)
    credencial_referencia = models.CharField(max_length=255, db_comment='Referencia a secreto (vault/keyring). NUNCA credencial en texto claro.')
    intervalo_sincronizacion_segundos = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = 'configuracion_integracion_zabbix'
        db_table_comment = 'Configuracion de integracion con Zabbix. La credencial se referencia, nunca se almacena en claro.'


class DecisionIntervencion(models.Model):
    id = models.BigAutoField(primary_key=True)
    intervencion = models.ForeignKey('Intervencion', models.DO_NOTHING)
    decisor = models.ForeignKey('Usuario', models.DO_NOTHING)
    decision = models.CharField(max_length=18)
    observacion = models.TextField(blank=True, null=True)
    fecha_hora = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'decision_intervencion'
        db_table_comment = 'Decisiones (aprobacion/rechazo) del flujo de una intervencion.'


class EntradaBitacora(models.Model):
    id = models.BigAutoField(primary_key=True)
    intervencion = models.ForeignKey('Intervencion', models.DO_NOTHING)
    autor = models.ForeignKey('Usuario', models.DO_NOTHING)
    contenido = models.TextField()
    fecha_hora = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'entrada_bitacora'
        db_table_comment = 'Entradas de bitacora de una intervencion.'


class EventoAcceso(models.Model):
    id = models.BigAutoField(primary_key=True)
    identificador_biometrico_externo = models.CharField(max_length=255)
    persona = models.ForeignKey('PersonaAutorizada', models.DB_SET_NULL, blank=True, null=True)
    punto_acceso = models.ForeignKey('PuntoAcceso', models.DO_NOTHING)
    fecha_hora = models.DateTimeField(db_comment='UTC (RNF-INT-02)')
    resultado = models.CharField(max_length=9)
    motivo = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'evento_acceso'
        db_table_comment = 'SOLO INSERCION (inmutable). Registro historico de eventos de acceso. La capa de datos DEBE impedir UPDATE/DELETE via permisos. persona_id NULLABLE + SET NULL: se conserva el evento aunque la persona sea desvinculada.'


class EventoTecnicoIngesta(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor_codigo = models.CharField(max_length=50)
    causa = models.CharField(max_length=255)
    contenido_no_sensible = models.JSONField(blank=True, null=True)
    fecha_hora = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'evento_tecnico_ingesta'
        db_table_comment = 'SOLO INSERCION. Eventos tecnicos de ingesta (diagnostico). La capa de datos DEBE impedir UPDATE/DELETE via permisos. No se referencia sensor_id por FK a proposito: registra el codigo aunque el sensor no exista aun.'


class EvidenciaAlerta(models.Model):
    id = models.BigAutoField(primary_key=True)
    alerta = models.ForeignKey(Alerta, models.DO_NOTHING)
    causa = models.CharField(max_length=500, blank=True, null=True)
    accion_ejecutada = models.TextField(blank=True, null=True)
    resultado = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey('Usuario', models.DO_NOTHING)
    fecha_hora = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'evidencia_alerta'
        db_table_comment = 'Evidencia/gestion de una alerta.'


class HistorialActivo(models.Model):
    id = models.BigAutoField(primary_key=True)
    activo = models.ForeignKey(Activo, models.DO_NOTHING)
    campo_modificado = models.CharField(max_length=100)
    valor_anterior = models.TextField(blank=True, null=True)
    valor_nuevo = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey('Usuario', models.DO_NOTHING)
    fecha_hora = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'historial_activo'
        db_table_comment = 'SOLO INSERCION (append-only). La capa de acceso a datos DEBE impedir UPDATE/DELETE mediante permisos de la cuenta de aplicacion (GRANT solo INSERT/SELECT); MySQL no bloquea updates por tabla de forma nativa.'


class HostProblemaZabbix(models.Model):
    id = models.BigAutoField(primary_key=True)
    identificador_externo = models.CharField(unique=True, max_length=255)
    activo = models.ForeignKey(Activo, models.DB_SET_NULL, blank=True, null=True)
    disponibilidad = models.CharField(max_length=50, blank=True, null=True)
    severidad = models.CharField(max_length=50, blank=True, null=True)
    estado = models.CharField(max_length=50, blank=True, null=True)
    fecha_ultima_sincronizacion = models.DateTimeField(blank=True, null=True, db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'host_problema_zabbix'
        db_table_comment = 'Hosts/problemas sincronizados desde Zabbix. activo_id NULLABLE + SET NULL: puede desvincularse del activo.'


class Intervencion(models.Model):
    id = models.BigAutoField(primary_key=True)
    objetivo = models.CharField(max_length=500)
    descripcion = models.TextField(blank=True, null=True)
    impacto_esperado = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateTimeField(blank=True, null=True, db_comment='UTC (RNF-INT-02)')
    fecha_termino = models.DateTimeField(blank=True, null=True, db_comment='UTC (RNF-INT-02)')
    responsable = models.ForeignKey('Usuario', models.DO_NOTHING)
    plan_reversa = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=18)

    class Meta:
        managed = False
        db_table = 'intervencion'
        db_table_comment = 'Intervenciones/cambios sobre activos (flujo de aprobacion y ejecucion).'


class IntervencionActivo(models.Model):
    id = models.BigAutoField(primary_key=True)
    intervencion = models.ForeignKey(Intervencion, models.DO_NOTHING)
    activo = models.ForeignKey(Activo, models.DO_NOTHING)
    estado_final_activo = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'intervencion_activo'
        unique_together = (('intervencion', 'activo'),)
        db_table_comment = 'Relacion N:M entre intervenciones y activos afectados.'


class Medicion(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey('Sensor', models.DO_NOTHING)
    evento_id = models.CharField(max_length=36, db_comment='UUID del evento para idempotencia.')
    temperatura = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    humedad = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    fecha_hora_medicion = models.DateTimeField(db_comment='UTC (RNF-INT-02). Marca de tiempo del sensor.')
    fecha_hora_recepcion = models.DateTimeField(db_comment='UTC (RNF-INT-02). Marca de tiempo de recepcion.')
    origen = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'medicion'
        unique_together = (('sensor', 'evento_id'),)
        db_table_comment = 'SOLO INSERCION (inmutable). La capa de datos DEBE impedir UPDATE/DELETE via permisos (GRANT solo INSERT/SELECT). Idempotencia por UNIQUE(sensor_id, evento_id). Alto volumen: hasta 43.200 registros/sensor/dia -> ver particionamiento sugerido al final.'


class Notificacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    alerta = models.ForeignKey(Alerta, models.DB_SET_NULL, blank=True, null=True)
    intervencion = models.ForeignKey(Intervencion, models.DB_SET_NULL, blank=True, null=True)
    canal = models.CharField(max_length=13)
    destinatario = models.CharField(max_length=255)
    fecha_envio = models.DateTimeField(db_comment='UTC (RNF-INT-02)')
    resultado = models.CharField(max_length=7)

    class Meta:
        managed = False
        db_table = 'notificacion'
        db_table_comment = 'Notificaciones emitidas por alerta o intervencion. FKs opcionales SET NULL.'


class PermisoAcceso(models.Model):
    id = models.BigAutoField(primary_key=True)
    persona = models.ForeignKey('PersonaAutorizada', models.DO_NOTHING)
    punto_acceso = models.ForeignKey('PuntoAcceso', models.DO_NOTHING)
    vigencia_inicio = models.DateField()
    vigencia_fin = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'permiso_acceso'
        db_table_comment = 'Permiso de acceso de una persona a un punto de acceso.'


class PermisoDia(models.Model):
    id = models.BigAutoField(primary_key=True)
    permiso_acceso = models.ForeignKey(PermisoAcceso, models.DB_CASCADE)
    dia_semana = models.CharField(max_length=3)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        managed = False
        db_table = 'permiso_dia'
        db_table_comment = 'Ventanas horarias por dia de un permiso de acceso. CASCADE: se elimina con el permiso padre.'


class PersonaAutorizada(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    identificador_biometrico_externo = models.CharField(unique=True, max_length=255)
    estado = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'persona_autorizada'
        db_table_comment = 'Personas autorizadas (identificador biometrico externo, sin datos biometricos crudos).'


class PuntoAcceso(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    ubicacion = models.ForeignKey('Ubicacion', models.DO_NOTHING)
    estado = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'punto_acceso'
        db_table_comment = 'Puntos de acceso fisico controlados por biometria.'


class ReglaAlerta(models.Model):
    id = models.BigAutoField(primary_key=True)
    fuente = models.CharField(max_length=100)
    condicion = models.CharField(max_length=500)
    severidad = models.CharField(max_length=11)
    destinatarios = models.JSONField(blank=True, null=True, db_comment='Lista de destinatarios en JSON. Alternativa normalizada: tabla regla_alerta_destinatario.')
    horario_notificacion = models.CharField(max_length=255, blank=True, null=True)
    version = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = 'regla_alerta'
        db_table_comment = 'Reglas de generacion/enrutamiento de alertas. Destinatarios en JSON (ver alternativa normalizada comentada al final).'


class ReservaRecurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    intervencion = models.ForeignKey(Intervencion, models.DO_NOTHING)
    activo = models.ForeignKey(Activo, models.DB_SET_NULL, blank=True, null=True)
    ubicacion = models.ForeignKey('Ubicacion', models.DB_SET_NULL, blank=True, null=True)
    fecha_inicio = models.DateTimeField(db_comment='UTC (RNF-INT-02)')
    fecha_fin = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'reserva_recurso'
        db_table_comment = 'Reservas de recurso (activo/ubicacion) para intervenciones. Indices para deteccion de solapamientos. Nota: la deteccion de solapamiento se resuelve en la capa de aplicacion o via CHECK/consultas; MySQL no soporta exclusion constraints por rango de forma nativa.'


class Sensor(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(unique=True, max_length=50)
    tipo = models.CharField(max_length=100)
    ubicacion = models.ForeignKey('Ubicacion', models.DO_NOTHING)
    estado = models.CharField(max_length=8)
    intervalo_esperado_segundos = models.PositiveIntegerField()
    device_key_hash = models.CharField(max_length=255, db_comment='Hash de la device key; nunca en texto claro.')

    class Meta:
        managed = False
        db_table = 'sensor'
        db_table_comment = 'Sensores IoT ambientales.'


class Ubicacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    sala = models.CharField(max_length=100)
    zona = models.CharField(max_length=100, blank=True, null=True)
    rack = models.CharField(max_length=100, blank=True, null=True)
    posicion = models.CharField(max_length=100, blank=True, null=True)
    ubicacion_padre = models.ForeignKey('self', models.DB_SET_NULL, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ubicacion'
        db_table_comment = 'Ubicaciones físicas jerárquicas (sala/zona/rack/posicion).'


class UmbralAmbiental(models.Model):
    id = models.BigAutoField(primary_key=True)
    ubicacion = models.ForeignKey(Ubicacion, models.DO_NOTHING)
    variable = models.CharField(max_length=11)
    valor_minimo = models.DecimalField(max_digits=6, decimal_places=2)
    valor_maximo = models.DecimalField(max_digits=6, decimal_places=2)
    version = models.PositiveIntegerField()
    vigente_desde = models.DateTimeField(db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'umbral_ambiental'
        db_table_comment = 'Umbrales ambientales versionados por ubicacion y variable.'


class Usuario(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    correo = models.CharField(unique=True, max_length=255)
    password_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=13)
    estado = models.CharField(max_length=8)
    fecha_ultimo_acceso = models.DateTimeField(blank=True, null=True, db_comment='UTC (RNF-INT-02)')

    class Meta:
        managed = False
        db_table = 'usuario'
        db_table_comment = 'Usuarios de la plataforma SICMA (no confundir con auth_user de Django).'
