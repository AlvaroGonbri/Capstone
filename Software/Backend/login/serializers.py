from datetime import timedelta

from django.contrib.auth import password_validation
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from .models import UserSessionSettings


User = get_user_model()

ROLE_NAMES = {
    'administrador': 'administrador',
    'administradorprivilegiado': 'administrador',
    'jefatura': 'jefatura',
    'tecnico': 'tecnico',
    'tecnicos': 'tecnico',
    'técnico': 'tecnico',
    'auditor': 'auditor',
    'auditores': 'auditor',
}


def get_user_role(user):
    roles = {
        ROLE_NAMES[name.strip().lower()]
        for name in user.groups.values_list('name', flat=True)
        if name.strip().lower() in ROLE_NAMES
    }
    if len(roles) != 1:
        raise AuthenticationFailed(
            'El usuario debe tener exactamente un rol asignado.'
        )
    return roles.pop()


def get_inactivity_timeout_minutes(user):
    return UserSessionSettings.objects.get_or_create(user=user)[0].inactivity_timeout_minutes


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = get_user_role(user)
        return token

    def validate(self, attrs):
        login = attrs.get(self.username_field, '').strip()
        user = User.objects.filter(email__iexact=login, is_active=True).first()
        if user:
            attrs[self.username_field] = user.get_username()
        data = super().validate(attrs)
        UserSessionSettings.objects.update_or_create(
            user=self.user,
            defaults={'last_activity_at': timezone.now()},
        )
        return data


class InactivityAwareTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        user = User.objects.filter(pk=refresh.get('user_id'), is_active=True).first()
        if user is None:
            raise AuthenticationFailed('El usuario no está activo.')
        session_settings = UserSessionSettings.objects.get_or_create(user=user)[0]
        if session_settings.last_activity_at is not None:
            elapsed = timezone.now() - session_settings.last_activity_at
            timeout = timedelta(minutes=session_settings.inactivity_timeout_minutes)
            if elapsed > timeout:
                raise AuthenticationFailed('La sesión expiró por inactividad.')
        data = super().validate(attrs)
        session_settings.last_activity_at = timezone.now()
        session_settings.save(update_fields=['last_activity_at'])
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        try:
            password_validation.validate_password(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class SessionTimeoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSessionSettings
        fields = ('inactivity_timeout_minutes',)

    def validate_inactivity_timeout_minutes(self, value):
        if not 1 <= value <= 120:
            raise serializers.ValidationError(
                'El tiempo de inactividad debe estar entre 1 y 120 minutos.'
            )
        return value


class ManagedUserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(write_only=True, required=True)
    rol = serializers.SerializerMethodField()
    inactivity_timeout_minutes = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=120,
    )

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'rol',
            'role',
            'inactivity_timeout_minutes',
            'password',
        )
        extra_kwargs = {'password': {'write_only': True, 'required': False}}

    def get_rol(self, user):
        try:
            return get_user_role(user)
        except AuthenticationFailed:
            return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['inactivity_timeout_minutes'] = get_inactivity_timeout_minutes(instance)
        return data

    def validate_role(self, value):
        normalized = value.strip().lower()
        if normalized == 'administradorprivilegiado':
            return 'AdministradorPrivilegiado'
        canonical = {
            'administrador': 'Administrador',
            'jefatura': 'Jefatura',
            'tecnico': 'Tecnico',
            'técnico': 'Tecnico',
            'auditor': 'Auditor',
        }.get(normalized)
        if canonical is None:
            raise serializers.ValidationError('El rol no es válido.')
        return canonical

    def create(self, validated_data):
        role = validated_data.pop('role')
        password = validated_data.pop('password', None)
        timeout = validated_data.pop('inactivity_timeout_minutes', 15)
        user = User(**validated_data)
        if not password:
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria.'})
        user.set_password(password)
        user.save()
        self._assign_role(user, role)
        UserSessionSettings.objects.create(user=user, inactivity_timeout_minutes=timeout)
        return user

    def update(self, user, validated_data):
        role = validated_data.pop('role', None)
        password = validated_data.pop('password', None)
        timeout = validated_data.pop('inactivity_timeout_minutes', None)
        for field, value in validated_data.items():
            setattr(user, field, value)
        if password:
            user.set_password(password)
        user.save()
        if role:
            self._assign_role(user, role)
        settings, _ = UserSessionSettings.objects.get_or_create(user=user)
        if timeout is not None:
            settings.inactivity_timeout_minutes = timeout
            settings.save(update_fields=['inactivity_timeout_minutes'])
        return user

    def _assign_role(self, user, role):
        user.groups.set([Group.objects.get_or_create(name=role)[0]])
