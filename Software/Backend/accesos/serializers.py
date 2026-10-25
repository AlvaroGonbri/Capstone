from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from mediciones.models import Ubicacion

from . import servicio
from .models import (
    ACTIVO,
    DENEGADO,
    DIAS_SEMANA,
    ERROR,
    INACTIVO,
    PERMITIDO,
    REVOCADO,
    CambioHabilitacion,
    EventoAcceso,
    PermisoAcceso,
    PermisoDia,
    PersonaAutorizada,
    PuntoAcceso,
    SolicitudEnrolamiento,
    SolicitudVerificacion,
)


User = get_user_model()


def nombre_ubicacion(ubicacion):
    return ' · '.join(filter(None, (ubicacion.sala, ubicacion.zona, ubicacion.rack, ubicacion.posicion)))


def nombre_usuario(usuario):
    return (usuario.get_full_name() or usuario.get_username()) if usuario else None


class SolicitudEnrolamientoSerializer(serializers.ModelSerializer):
    punto_nombre = serializers.CharField(source='punto_acceso.nombre', read_only=True)
    solicitada_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudEnrolamiento
        fields = (
            'id', 'persona', 'punto_acceso', 'punto_nombre', 'estado', 'mensaje', 'solicitada_por_nombre',
            'fecha_solicitud', 'fecha_inicio', 'fecha_fin', 'muestra', 'total_muestras', 'indicacion',
        )

    def get_solicitada_por_nombre(self, solicitud):
        return nombre_usuario(solicitud.solicitada_por)


class PersonaSerializer(serializers.ModelSerializer):
    """Ficha de la persona (RF-ACC-02). La registra el Departamento de contratistas o el Administrador.

    El identificador de huella lo genera SICMA (EXT-00001) si no se indica. La habilitación (estado)
    no se edita aquí: se cambia con /habilitacion/, que exige motivo y deja historial.
    """

    usuario = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    usuario_nombre = serializers.SerializerMethodField()
    identificador_biometrico_externo = serializers.CharField(max_length=255, required=False, allow_blank=True)
    rut = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    empresa = serializers.CharField(max_length=150, required=False, allow_null=True, allow_blank=True)
    huella_registrada_por_nombre = serializers.SerializerMethodField()
    enrolamiento = serializers.SerializerMethodField()

    class Meta:
        model = PersonaAutorizada
        fields = (
            'id', 'nombre', 'rut', 'empresa', 'identificador_biometrico_externo', 'estado', 'usuario',
            'usuario_nombre', 'huella_registrada_en', 'huella_registrada_por_nombre', 'enrolamiento',
        )
        read_only_fields = ('estado', 'huella_registrada_en')

    def get_usuario_nombre(self, persona):
        return nombre_usuario(persona.usuario)

    def get_huella_registrada_por_nombre(self, persona):
        return nombre_usuario(persona.huella_registrada_por)

    def get_enrolamiento(self, persona):
        """La última solicitud de enrolamiento: la vista muestra si está en curso o por qué falló."""
        ultima = max(persona.enrolamientos.all(), key=lambda s: s.id, default=None)
        return SolicitudEnrolamientoSerializer(ultima).data if ultima else None

    def validate_identificador_biometrico_externo(self, valor):
        valor = valor.strip()
        if self.instance and valor and valor != self.instance.identificador_biometrico_externo:
            raise serializers.ValidationError('El identificador no se cambia: las huellas enroladas lo usan.')
        if valor == servicio.IDENTIFICADOR_DESCONOCIDO or valor.startswith('TMP-'):
            raise serializers.ValidationError('Identificador no válido.')
        if valor and PersonaAutorizada.objects.filter(identificador_biometrico_externo=valor).exclude(
            pk=getattr(self.instance, 'pk', None),
        ).exists():
            raise serializers.ValidationError('Ya existe una persona con este identificador.')
        return valor

    def validate_rut(self, valor):
        if not valor:
            return None
        try:
            rut = servicio.normalizar_rut(valor)
        except ValueError as error:
            raise serializers.ValidationError(str(error)) from error
        if PersonaAutorizada.objects.filter(rut=rut).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError('Ya existe una persona con este RUT.')
        return rut

    def validate_empresa(self, valor):
        return (valor or '').strip() or None

    def validate_nombre(self, valor):
        return valor.strip()

    def create(self, datos):
        return servicio.crear_persona(datos)


class HabilitacionSerializer(serializers.Serializer):
    habilitada = serializers.BooleanField()
    motivo = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate(self, datos):
        if not datos['habilitada'] and not datos['motivo'].strip():
            raise serializers.ValidationError({'motivo': 'Indica por qué se deshabilita (p. ej. cotizaciones vencidas).'})
        return datos


class CambioHabilitacionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CambioHabilitacion
        fields = ('habilitada', 'motivo', 'usuario_nombre', 'fecha_hora')

    def get_usuario_nombre(self, cambio):
        return nombre_usuario(cambio.usuario)


class SolicitarEnrolamientoSerializer(serializers.Serializer):
    # Opcional si hay un solo lector activo.
    punto_acceso = serializers.PrimaryKeyRelatedField(queryset=PuntoAcceso.objects.filter(estado=ACTIVO), required=False)


class SolicitudVerificacionSerializer(serializers.ModelSerializer):
    punto_nombre = serializers.CharField(source='punto_acceso.nombre', read_only=True)

    class Meta:
        model = SolicitudVerificacion
        fields = (
            'id', 'persona', 'intervencion_id', 'punto_acceso', 'punto_nombre', 'estado', 'mensaje', 'identificado',
            'intento', 'total_intentos', 'indicacion', 'fecha_solicitud', 'fecha_fin',
        )


class ProgresoVerificacionSerializer(serializers.Serializer):
    intento = serializers.IntegerField(min_value=1, max_value=20)
    total_intentos = serializers.IntegerField(min_value=1, max_value=20)
    indicacion = serializers.CharField(max_length=120)


class ResultadoVerificacionSerializer(serializers.Serializer):
    coincide = serializers.BooleanField()
    identificado = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True, default='')
    mensaje = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class ProgresoEnrolamientoSerializer(serializers.Serializer):
    muestra = serializers.IntegerField(min_value=1, max_value=20)
    total_muestras = serializers.IntegerField(min_value=1, max_value=20)
    indicacion = serializers.CharField(max_length=120)


class ResultadoEnrolamientoSerializer(serializers.Serializer):
    exito = serializers.BooleanField()
    mensaje = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class PuntoAccesoSerializer(serializers.ModelSerializer):
    estado = serializers.ChoiceField(choices=(ACTIVO, INACTIVO), required=False)
    ubicacion = serializers.PrimaryKeyRelatedField(queryset=Ubicacion.objects.all())
    ubicacion_nombre = serializers.SerializerMethodField()
    tiene_clave = serializers.SerializerMethodField()

    class Meta:
        model = PuntoAcceso
        fields = ('id', 'nombre', 'ubicacion', 'ubicacion_nombre', 'estado', 'tiene_clave')

    def get_ubicacion_nombre(self, punto):
        return nombre_ubicacion(punto.ubicacion)

    def get_tiene_clave(self, punto):
        return bool(punto.device_key_hash)


class PermisoDiaSerializer(serializers.ModelSerializer):
    dia_semana = serializers.ChoiceField(choices=DIAS_SEMANA)

    class Meta:
        model = PermisoDia
        fields = ('dia_semana', 'hora_inicio', 'hora_fin')


class PermisoSerializer(serializers.ModelSerializer):
    """Permiso de una persona en un punto, con vigencia y ventanas horarias opcionales.

    Revocar = estado 'Revocado' (no se borra, para conservar la trazabilidad).
    """

    estado = serializers.ChoiceField(choices=(ACTIVO, REVOCADO), required=False)
    persona = serializers.PrimaryKeyRelatedField(queryset=PersonaAutorizada.objects.all())
    punto_acceso = serializers.PrimaryKeyRelatedField(queryset=PuntoAcceso.objects.all())
    dias = PermisoDiaSerializer(many=True, required=False)
    persona_nombre = serializers.CharField(source='persona.nombre', read_only=True)
    punto_nombre = serializers.CharField(source='punto_acceso.nombre', read_only=True)

    class Meta:
        model = PermisoAcceso
        fields = (
            'id', 'persona', 'persona_nombre', 'punto_acceso', 'punto_nombre', 'vigencia_inicio',
            'vigencia_fin', 'estado', 'dias',
        )

    def validate(self, datos):
        inicio = datos.get('vigencia_inicio', getattr(self.instance, 'vigencia_inicio', None))
        fin = datos.get('vigencia_fin', getattr(self.instance, 'vigencia_fin', None))
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError({'vigencia_fin': 'Debe ser igual o posterior al inicio.'})
        return datos

    def create(self, datos):
        dias = datos.pop('dias', [])
        with transaction.atomic():
            permiso = PermisoAcceso.objects.create(**datos)
            PermisoDia.objects.bulk_create([PermisoDia(permiso=permiso, **d) for d in dias])
        return permiso

    def update(self, permiso, datos):
        dias = datos.pop('dias', None)
        with transaction.atomic():
            for campo, valor in datos.items():
                setattr(permiso, campo, valor)
            permiso.save()
            if dias is not None:  # las ventanas se reemplazan completas
                permiso.dias.all().delete()
                PermisoDia.objects.bulk_create([PermisoDia(permiso=permiso, **d) for d in dias])
        return permiso


class EventoSerializer(serializers.ModelSerializer):
    persona_nombre = serializers.SerializerMethodField()
    punto_nombre = serializers.CharField(source='punto_acceso.nombre', read_only=True)
    ubicacion_nombre = serializers.SerializerMethodField()

    class Meta:
        model = EventoAcceso
        fields = (
            'id', 'fecha_hora', 'resultado', 'motivo', 'identificador_biometrico_externo', 'persona',
            'persona_nombre', 'punto_acceso', 'punto_nombre', 'ubicacion_nombre',
        )

    def get_persona_nombre(self, evento):
        return evento.persona.nombre if evento.persona else None

    def get_ubicacion_nombre(self, evento):
        return nombre_ubicacion(evento.punto_acceso.ubicacion)


class EventoFiltroSerializer(serializers.Serializer):
    """RF-ACC-03: el Auditor filtra por fecha, resultado, punto y persona."""

    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    resultado = serializers.ChoiceField(choices=(PERMITIDO, DENEGADO, ERROR), required=False)
    punto = serializers.IntegerField(required=False, min_value=1)
    persona = serializers.IntegerField(required=False, min_value=1)
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)


class IntentoLectorSerializer(serializers.Serializer):
    """Lo que envía el agente del lector. Nunca incluye datos biométricos."""

    evento_id = serializers.UUIDField()
    estado = serializers.ChoiceField(choices=(servicio.COINCIDE, servicio.SIN_COINCIDENCIA, servicio.FALLA_LECTOR))
    identificador = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    fecha_hora = serializers.DateTimeField(required=False)
    motivo = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')

    def validate(self, datos):
        if datos['estado'] == servicio.COINCIDE and not datos['identificador'].strip():
            raise serializers.ValidationError({'identificador': 'Requerido cuando la huella coincide.'})
        ahora = timezone.now()
        fecha = datos.get('fecha_hora') or ahora
        # Un evento del futuro o de hace más de un día no es creíble: se registra con la hora de llegada.
        if fecha > ahora + timedelta(minutes=5) or fecha < ahora - timedelta(days=1):
            fecha = ahora
        datos['fecha_hora'] = fecha
        return datos
