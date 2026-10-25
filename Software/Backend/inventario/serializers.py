from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from mediciones.models import Ubicacion

from .models import CRITICIDADES, Activo, EstadoActivo, HistorialActivo, TipoActivo


User = get_user_model()

# Campos cuyo cambio queda en el historial (RF-ACT-03).
CAMPOS_HISTORIAL = (
    'codigo', 'nombre', 'tipo', 'marca', 'modelo', 'numero_serie',
    'estado', 'criticidad', 'ubicacion', 'responsable', 'observaciones',
)


def nombre_ubicacion(ubicacion):
    return ' · '.join(filter(None, (ubicacion.sala, ubicacion.zona, ubicacion.rack, ubicacion.posicion)))


def nombre_usuario(usuario):
    return (usuario.get_full_name() or usuario.get_username()) if usuario else None


def _texto(activo, campo):
    """Valor legible de un campo para el historial."""
    valor = getattr(activo, campo)
    if campo == 'ubicacion':
        return nombre_ubicacion(valor)
    if campo == 'responsable':
        return nombre_usuario(valor)
    return None if valor in (None, '') else str(valor)


class TipoActivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoActivo
        fields = ('id', 'nombre', 'activo')


# Colores de Ionic que acepta un estado (se usan en las insignias del frontend).
COLORES_ESTADO = ('primary', 'secondary', 'tertiary', 'success', 'warning', 'danger', 'medium', 'dark')


class EstadoActivoSerializer(serializers.ModelSerializer):
    """Estados de activo (RF-CAT-03). El nombre es la clave que guarda cada activo y su historial,
    por eso no cambia después del alta; lo que se muestra es la etiqueta."""

    color = serializers.ChoiceField(choices=COLORES_ESTADO, required=False)
    etiqueta = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = EstadoActivo
        fields = ('id', 'nombre', 'etiqueta', 'color', 'activo', 'es_sistema', 'orden')
        read_only_fields = ('es_sistema',)

    def validate_nombre(self, nombre):
        nombre = nombre.strip()
        if self.instance and nombre != self.instance.nombre:
            raise serializers.ValidationError('El nombre de un estado no se puede cambiar; edita su etiqueta.')
        return nombre

    def validate_activo(self, activo):
        estado = self.instance
        if estado and not activo and estado.activo:
            if estado.es_sistema:
                raise serializers.ValidationError('Este estado lo usa el sistema y no se puede desactivar.')
            if Activo.objects.filter(estado=estado.nombre).exists():
                raise serializers.ValidationError('Hay activos en este estado; cámbialos antes de desactivarlo.')
        return activo

    def validate(self, datos):
        if not self.instance and not datos.get('etiqueta'):
            datos['etiqueta'] = datos['nombre'].replace('_', ' ')
        if 'etiqueta' in datos and not datos['etiqueta'].strip():
            raise serializers.ValidationError({'etiqueta': 'La etiqueta no puede quedar vacía.'})
        return datos


class ActivoReadSerializer(serializers.ModelSerializer):
    ubicacion_nombre = serializers.SerializerMethodField()
    responsable_nombre = serializers.SerializerMethodField()
    responsable_email = serializers.SerializerMethodField()

    class Meta:
        model = Activo
        fields = (
            'id', 'codigo', 'nombre', 'tipo', 'marca', 'modelo', 'numero_serie', 'estado',
            'criticidad', 'ubicacion', 'ubicacion_nombre', 'responsable', 'responsable_nombre',
            'responsable_email', 'fecha_alta', 'observaciones',
        )

    def get_ubicacion_nombre(self, activo):
        return nombre_ubicacion(activo.ubicacion)

    def get_responsable_nombre(self, activo):
        return nombre_usuario(activo.responsable)

    def get_responsable_email(self, activo):
        return activo.responsable.email if activo.responsable else None


class ActivoWriteSerializer(serializers.ModelSerializer):
    """Alta y edición de activos (RF-ACT-01, RF-ACT-04). Dar de baja = estado 'Retirado' (RN-02)."""

    estado = serializers.CharField(max_length=50, required=False)
    criticidad = serializers.ChoiceField(choices=CRITICIDADES, required=False)
    ubicacion = serializers.PrimaryKeyRelatedField(queryset=Ubicacion.objects.all())
    responsable = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True,
    )
    tipo = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Activo
        fields = (
            'codigo', 'nombre', 'tipo', 'marca', 'modelo', 'numero_serie', 'estado',
            'criticidad', 'ubicacion', 'responsable', 'observaciones',
        )

    def validate_tipo(self, tipo):
        if not tipo:
            return None
        if self.instance and tipo == self.instance.tipo:
            return tipo  # un tipo que luego se desactivó se puede conservar
        if not TipoActivo.objects.filter(nombre=tipo, activo=True).exists():
            raise serializers.ValidationError('El tipo no existe en el catálogo o está desactivado.')
        return tipo

    def validate_estado(self, estado):
        if self.instance and estado == self.instance.estado:
            return estado  # un estado que luego se desactivó se puede conservar
        # Dar de baja (o reincorporar) un activo es una decisión de gestión: solo administradores.
        from login.permissions import ADMIN_ROLES
        from login.serializers import get_user_role
        from rest_framework.exceptions import PermissionDenied

        from .models import ESTADO_RETIRADO

        actual = self.instance.estado if self.instance else None
        if ESTADO_RETIRADO in (estado, actual) and get_user_role(self.context['request'].user) not in ADMIN_ROLES:
            raise PermissionDenied('Solo un Administrador puede dar de baja o reincorporar un activo.')
        if not EstadoActivo.objects.filter(nombre=estado, activo=True).exists():
            raise serializers.ValidationError('El estado no existe en el catálogo o está desactivado.')
        return estado

    def validate_ubicacion(self, ubicacion):
        cambia = not self.instance or self.instance.ubicacion_id != ubicacion.pk
        if cambia and not ubicacion.activa:
            raise serializers.ValidationError('La ubicación está desactivada.')
        return ubicacion

    def create(self, validated_data):
        usuario = self.context['request'].user
        with transaction.atomic():
            activo = Activo.objects.create(**validated_data, fecha_alta=timezone.now())
            HistorialActivo.objects.create(
                activo=activo, campo_modificado='alta', valor_anterior=None,
                valor_nuevo=f'{activo.codigo} · {activo.nombre}', usuario=usuario,
                fecha_hora=activo.fecha_alta,
            )
        return activo

    def update(self, activo, validated_data):
        usuario = self.context['request'].user
        antes = {campo: _texto(activo, campo) for campo in CAMPOS_HISTORIAL}
        for campo, valor in validated_data.items():
            setattr(activo, campo, valor)
        ahora = timezone.now()
        with transaction.atomic():
            activo.save()
            HistorialActivo.objects.bulk_create([
                HistorialActivo(
                    activo=activo, campo_modificado=campo, valor_anterior=antes[campo],
                    valor_nuevo=_texto(activo, campo), usuario=usuario, fecha_hora=ahora,
                )
                for campo in CAMPOS_HISTORIAL
                if campo in validated_data and antes[campo] != _texto(activo, campo)
            ])
        return activo


class HistorialActivoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialActivo
        fields = ('id', 'campo_modificado', 'valor_anterior', 'valor_nuevo', 'usuario_nombre', 'fecha_hora')

    def get_usuario_nombre(self, registro):
        return nombre_usuario(registro.usuario)


class ActivoFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    tipo = serializers.CharField(required=False, max_length=100)
    ubicacion = serializers.IntegerField(required=False, min_value=1)
    estado = serializers.CharField(required=False, max_length=50)
    incluir_retirados = serializers.BooleanField(required=False, default=False)
