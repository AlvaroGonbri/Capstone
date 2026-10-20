from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from alertas.models import Notificacion
from inventario.models import Activo
from login.serializers import get_user_role

from .models import DecisionIntervencion, Intervencion


User = get_user_model()

# Pueden quedar a cargo de una intervención: técnicos y administradores.
ROLES_ASIGNABLES = ('tecnico', 'administrador', 'administradorprivilegiado')


def nombre_usuario(usuario):
    return (usuario.get_full_name() or usuario.get_username()) if usuario else None


def rol_de(usuario):
    try:
        return get_user_role(usuario)
    except AuthenticationFailed:
        return None


class DecisionSerializer(serializers.ModelSerializer):
    decisor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = DecisionIntervencion
        fields = ('decision', 'decisor_correo', 'decisor_nombre', 'observacion', 'fecha_hora')

    def get_decisor_nombre(self, decision):
        return nombre_usuario(decision.decisor)


class IntervencionSerializer(serializers.ModelSerializer):
    responsable_nombre = serializers.SerializerMethodField()
    activos = serializers.SerializerMethodField()
    decisiones = DecisionSerializer(many=True, read_only=True)
    agenda_enviada = serializers.SerializerMethodField()

    class Meta:
        model = Intervencion
        fields = (
            'id', 'objetivo', 'descripcion', 'impacto_esperado', 'plan_reversa', 'rack', 'solicitante_nombre',
            'solicitante_correo', 'estado', 'fecha_solicitud', 'fecha_inicio', 'fecha_termino',
            'fecha_cierre', 'observacion_cierre', 'responsable', 'responsable_nombre', 'activos',
            'decisiones', 'agenda_enviada',
        )

    def get_responsable_nombre(self, intervencion):
        return nombre_usuario(intervencion.responsable)

    def get_activos(self, intervencion):
        return [
            {'id': ia.activo.id, 'codigo': ia.activo.codigo, 'nombre': ia.activo.nombre}
            for ia in intervencion.activos_afectados.all()
        ]

    def get_agenda_enviada(self, intervencion):
        """True si SICMA ya pidió al flujo agendarla en Outlook (RF-INT-05)."""
        return Notificacion.objects.filter(
            intervencion_id=intervencion.id, canal='PowerAutomate', resultado='Enviado',
        ).exists()


class AsignacionSerializer(serializers.Serializer):
    tecnico = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    fecha_inicio = serializers.DateTimeField()
    fecha_termino = serializers.DateTimeField()
    activos = serializers.PrimaryKeyRelatedField(queryset=Activo.objects.all(), many=True, required=False)

    def validate_tecnico(self, tecnico):
        if rol_de(tecnico) not in ROLES_ASIGNABLES:
            raise serializers.ValidationError('El usuario debe ser Técnico o Administrador.')
        return tecnico

    def validate(self, datos):
        if datos['fecha_termino'] <= datos['fecha_inicio']:
            raise serializers.ValidationError({'fecha_termino': 'Debe ser posterior al inicio.'})
        return datos


class CierreSerializer(serializers.Serializer):
    exitosa = serializers.BooleanField()
    observacion = serializers.CharField(max_length=4000)


class CancelacionSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=4000)
