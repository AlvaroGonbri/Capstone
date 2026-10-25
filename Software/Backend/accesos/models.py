"""Control de acceso físico (RF-ACC). Tablas del script SQL del equipo (managed=False), ampliadas por 0001.

SICMA no guarda huellas: el agente del lector compara la huella en su PC y envía solo el
identificador que reconoció. SICMA decide si el acceso se permite y registra el intento.
"""
from django.conf import settings
from django.db import models


ACTIVO = 'Activo'
INACTIVO = 'Inactivo'
REVOCADO = 'Revocado'
PERMITIDO = 'Permitido'
DENEGADO = 'Denegado'
ERROR = 'Error'
DIAS_SEMANA = ('Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom')  # índice = date.weekday()


class PersonaAutorizada(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    # Con este identificador enrola el agente del lector (RF-ACC-02); nunca es un dato biométrico.
    identificador_biometrico_externo = models.CharField(max_length=255, unique=True)
    estado = models.CharField(max_length=8, default=ACTIVO)
    # Columna agregada por 0001: la persona puede ser además un usuario de SICMA.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column='usuario_id', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='persona_autorizada',
    )
    # Columnas agregadas por 0002: ficha del personal externo que registra el Departamento de contratistas.
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)  # normalizado: 12345678-K
    empresa = models.CharField(max_length=150, null=True, blank=True)
    huella_registrada_en = models.DateTimeField(null=True, blank=True)
    huella_registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column='huella_registrada_por_id', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

    class Meta:
        managed = False
        db_table = 'persona_autorizada'


class CambioHabilitacion(models.Model):
    """Alta o baja manual de una persona por el Departamento de contratistas (p. ej. cotizaciones al día).

    Solo inserción: es la trazabilidad de quién habilitó o deshabilitó a quién, cuándo y por qué.
    """

    # db_constraint=False: el id de persona_autorizada es BIGINT UNSIGNED y MySQL no admite la FK desde un BIGINT.
    persona = models.ForeignKey(PersonaAutorizada, on_delete=models.CASCADE, db_constraint=False, related_name='cambios_habilitacion')
    habilitada = models.BooleanField()
    motivo = models.CharField(max_length=255, blank=True, default='')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_hora = models.DateTimeField()

    class Meta:
        db_table = 'cambio_habilitacion'
        ordering = ['-fecha_hora', '-id']


# Estados de una solicitud de enrolamiento.
ENROL_PENDIENTE = 'Pendiente'
ENROL_EN_CURSO = 'EnCurso'
ENROL_COMPLETADA = 'Completada'
ENROL_FALLIDA = 'Fallida'
ENROL_CANCELADA = 'Cancelada'
ENROL_ABIERTAS = (ENROL_PENDIENTE, ENROL_EN_CURSO)


class SolicitudEnrolamiento(models.Model):
    """SICMA pide al agente de un lector que capture la huella de una persona.

    El navegador no puede usar el lector USB: la vista de SICMA crea la solicitud, el agente la toma en
    su próxima consulta, captura la huella (que queda solo en su PC) e informa el resultado.
    """

    persona = models.ForeignKey(PersonaAutorizada, on_delete=models.CASCADE, db_constraint=False, related_name='enrolamientos')
    punto_acceso = models.ForeignKey('PuntoAcceso', on_delete=models.CASCADE, db_constraint=False, related_name='enrolamientos')
    estado = models.CharField(max_length=10, default=ENROL_PENDIENTE)
    mensaje = models.CharField(max_length=255, blank=True, default='')
    solicitada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_solicitud = models.DateTimeField()
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    # Lo que el agente pide en este momento ("Apoya el dedo"), para mostrarlo en la pantalla de SICMA.
    muestra = models.PositiveSmallIntegerField(default=0)
    total_muestras = models.PositiveSmallIntegerField(default=3)
    indicacion = models.CharField(max_length=120, blank=True, default='')

    class Meta:
        db_table = 'solicitud_enrolamiento'
        ordering = ['-id']


class SolicitudVerificacion(models.Model):
    """SICMA pide al agente que confirme que la huella apoyada es la de UNA persona concreta.

    Se usa al iniciar una intervención: el personal externo demuestra que es quien fue asignado.
    """

    persona = models.ForeignKey(PersonaAutorizada, on_delete=models.CASCADE, db_constraint=False, related_name='verificaciones')
    punto_acceso = models.ForeignKey('PuntoAcceso', on_delete=models.CASCADE, db_constraint=False, related_name='verificaciones')
    intervencion_id = models.BigIntegerField(null=True, blank=True)  # a qué intervención corresponde
    estado = models.CharField(max_length=10, default=ENROL_PENDIENTE)  # mismos estados que el enrolamiento
    mensaje = models.CharField(max_length=255, blank=True, default='')
    # Identificador cuya huella apareció (el propio, el de otra persona o vacío si no coincidió con nadie).
    identificado = models.CharField(max_length=255, blank=True, default='')
    intento = models.PositiveSmallIntegerField(default=0)
    total_intentos = models.PositiveSmallIntegerField(default=3)
    indicacion = models.CharField(max_length=120, blank=True, default='')
    solicitada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_solicitud = models.DateTimeField()
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'solicitud_verificacion'
        ordering = ['-id']


BAJA_PENDIENTE = 'Pendiente'
BAJA_COMPLETADA = 'Completada'
BAJA_FALLIDA = 'Fallida'


class BajaHuella(models.Model):
    """Orden al agente de un lector para borrar de su PC la huella de una persona eliminada de SICMA.

    No apunta a la persona (ya no existe): guarda su identificador y su nombre para la trazabilidad.
    """

    punto_acceso = models.ForeignKey('PuntoAcceso', on_delete=models.CASCADE, db_constraint=False, related_name='bajas_huella')
    identificador = models.CharField(max_length=255)
    nombre = models.CharField(max_length=150)
    estado = models.CharField(max_length=10, default=BAJA_PENDIENTE)
    mensaje = models.CharField(max_length=255, blank=True, default='')
    solicitada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_solicitud = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'baja_huella'
        ordering = ['id']


class PuntoAcceso(models.Model):
    """Un lector biométrico (p. ej. la puerta de la sala). El agente se autentica con su clave."""

    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    ubicacion = models.ForeignKey(
        'mediciones.Ubicacion', db_column='ubicacion_id', on_delete=models.DO_NOTHING, related_name='puntos_acceso',
    )
    estado = models.CharField(max_length=8, default=ACTIVO)
    # Columna agregada por 0001: hash de la clave del agente (igual que en los sensores).
    device_key_hash = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'punto_acceso'


class PermisoAcceso(models.Model):
    id = models.BigAutoField(primary_key=True)
    persona = models.ForeignKey(PersonaAutorizada, db_column='persona_id', on_delete=models.DO_NOTHING, related_name='permisos')
    punto_acceso = models.ForeignKey(PuntoAcceso, db_column='punto_acceso_id', on_delete=models.DO_NOTHING, related_name='permisos')
    vigencia_inicio = models.DateField()
    vigencia_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=8, default=ACTIVO)  # Activo | Revocado

    class Meta:
        managed = False
        db_table = 'permiso_acceso'


class PermisoDia(models.Model):
    """Ventana horaria de un permiso. Un permiso sin ventanas vale todo el día, todos los días."""

    id = models.BigAutoField(primary_key=True)
    permiso = models.ForeignKey(PermisoAcceso, db_column='permiso_acceso_id', on_delete=models.CASCADE, related_name='dias')
    dia_semana = models.CharField(max_length=3)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        managed = False
        db_table = 'permiso_dia'


class EventoAcceso(models.Model):
    """Intento de acceso (RF-ACC-01). Solo inserción: la API no permite editarlo ni borrarlo."""

    id = models.BigAutoField(primary_key=True)
    identificador_biometrico_externo = models.CharField(max_length=255)
    persona = models.ForeignKey(
        PersonaAutorizada, db_column='persona_id', on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos',
    )
    punto_acceso = models.ForeignKey(PuntoAcceso, db_column='punto_acceso_id', on_delete=models.DO_NOTHING, related_name='eventos')
    fecha_hora = models.DateTimeField()
    resultado = models.CharField(max_length=9)  # Permitido | Denegado | Error
    motivo = models.CharField(max_length=255, null=True, blank=True)
    # Columna agregada por 0001: id que genera el agente, para que un reintento no duplique el evento.
    evento_externo_id = models.CharField(max_length=36, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'evento_acceso'
        unique_together = ('punto_acceso', 'evento_externo_id')
