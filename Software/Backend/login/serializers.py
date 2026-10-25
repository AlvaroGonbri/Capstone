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

from . import bloqueo
from .authentication import CLAIM_SOLO_LECTURA
from .models import PasswordPolicy, UserSessionSettings
from .passwords import (
    PasswordExpired,
    mark_password_changed,
    password_expires_at,
    password_is_expired,
)


User = get_user_model()

ROLE_NAMES = {
    'administrador': 'administrador',
    'administradorprivilegiado': 'administradorprivilegiado',
    'jefatura': 'jefatura',
    'tecnico': 'tecnico',
    'tecnicos': 'tecnico',
    'técnico': 'tecnico',
    'auditor': 'auditor',
    'auditores': 'auditor',
    # Departamento de contratistas: enrola y habilita al personal externo (RF-ACC).
    'contratistas': 'contratistas',
    'contratista': 'contratistas',
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
    # 'movil': la app móvil recibe tokens de solo lectura (RF-PLT-02). El claim viaja en el
    # refresh token, así que también lo heredan los access tokens renovados.
    canal = serializers.ChoiceField(choices=('web', 'movil'), required=False, default='web')

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = get_user_role(user)
        return token

    def validate(self, attrs):
        canal = attrs.pop('canal', 'web')
        data = self._validar_credenciales(attrs)
        if canal == 'movil':
            refresh = self.get_token(self.user)
            refresh[CLAIM_SOLO_LECTURA] = True
            data['refresh'], data['access'] = str(refresh), str(refresh.access_token)
        return data

    def _validar_credenciales(self, attrs):
        login = attrs.get(self.username_field, '').strip()
        user = User.objects.filter(email__iexact=login, is_active=True).first()
        if user:
            attrs[self.username_field] = user.get_username()
        else:
            user = User.objects.filter(username=login, is_active=True).first()
        if user:
            bloqueo.comprobar(user)  # bloqueada: ni siquiera se prueba la contraseña
        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            if user:
                bloqueo.registrar_fallo(user)
            raise
        bloqueo.registrar_exito(self.user)
        # Se revisa después de validar la clave, para no revelar el estado de cuentas ajenas.
        if password_is_expired(self.user):
            raise PasswordExpired()
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
        if password_is_expired(user):
            raise PasswordExpired()
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


class PasswordChangeSerializer(serializers.Serializer):
    """Cambio de contraseña con la clave actual; sirve también cuando ya expiró."""

    username = serializers.CharField()
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        login = attrs['username'].strip()
        user = (
            User.objects.filter(email__iexact=login, is_active=True).first()
            or User.objects.filter(username=login, is_active=True).first()
        )
        if user is not None:
            bloqueo.comprobar(user)
        if user is None or not user.check_password(attrs['current_password']):
            if user is not None:
                bloqueo.registrar_fallo(user)
            raise serializers.ValidationError(
                {'detail': 'El usuario o la contraseña actual no son correctos.'}
            )
        bloqueo.registrar_exito(user)
        if attrs['new_password'] == attrs['current_password']:
            raise serializers.ValidationError(
                {'new_password': 'La nueva contraseña debe ser distinta de la actual.'}
            )
        try:
            password_validation.validate_password(attrs['new_password'], user)
        except ValidationError as exc:
            raise serializers.ValidationError({'new_password': exc.messages}) from exc
        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        mark_password_changed(user)
        return user


class PasswordPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PasswordPolicy
        fields = ('max_age_days',)

    def validate_max_age_days(self, value):
        if not 0 <= value <= 365:
            raise serializers.ValidationError(
                'La vigencia debe estar entre 0 (sin expiración) y 365 días.'
            )
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
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    rol = serializers.SerializerMethodField()
    inactivity_timeout_minutes = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=120,
    )
    password_never_expires = serializers.BooleanField(required=False)

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
            'password_never_expires',
            'password',
        )

    def get_rol(self, user):
        try:
            return get_user_role(user)
        except AuthenticationFailed:
            return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        session_settings = UserSessionSettings.objects.get_or_create(user=instance)[0]
        policy = self.context.get('password_policy') or PasswordPolicy.get_solo()
        expires_at = password_expires_at(instance, policy)
        data['inactivity_timeout_minutes'] = session_settings.inactivity_timeout_minutes
        data['password_never_expires'] = session_settings.password_never_expires
        data['password_changed_at'] = session_settings.password_changed_at
        data['password_expires_at'] = expires_at
        data['password_expired'] = expires_at is not None and timezone.now() >= expires_at
        return data

    def validate(self, attrs):
        """Un Administrador (no Privilegiado) no toca cuentas de administración ni la seguridad de las sesiones.

        Evita que se otorgue a sí mismo, o a otro, más privilegios de los que tiene.
        """
        from rest_framework.exceptions import PermissionDenied

        from .permissions import GRUPOS_ADMINISTRACION, es_privilegiado

        solicitante = self.context.get('request').user if self.context.get('request') else None
        if solicitante is None or es_privilegiado(solicitante):
            return attrs
        if attrs.get('role') in GRUPOS_ADMINISTRACION:
            raise PermissionDenied('Solo un Administrador Privilegiado puede asignar roles de administración.')
        if self.instance is not None and self.instance.groups.filter(name__in=GRUPOS_ADMINISTRACION).exists():
            raise PermissionDenied('Solo un Administrador Privilegiado puede modificar cuentas de administración.')
        actuales = UserSessionSettings.objects.filter(user=self.instance).first() if self.instance else None
        timeout_actual = actuales.inactivity_timeout_minutes if actuales else 15
        nunca_actual = actuales.password_never_expires if actuales else False
        if attrs.get('inactivity_timeout_minutes', timeout_actual) != timeout_actual or \
                attrs.get('password_never_expires', nunca_actual) != nunca_actual:
            raise PermissionDenied('Solo un Administrador Privilegiado cambia la inactividad y la vigencia de contraseñas.')
        return attrs

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
            'contratistas': 'Contratistas',
        }.get(normalized)
        if canonical is None:
            raise serializers.ValidationError('El rol no es válido.')
        return canonical

    def create(self, validated_data):
        role = validated_data.pop('role')
        password = validated_data.pop('password', None)
        timeout = validated_data.pop('inactivity_timeout_minutes', 15)
        never_expires = validated_data.pop('password_never_expires', False)
        user = User(**validated_data)
        if not password:
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria.'})
        user.set_password(password)
        user.save()
        self._assign_role(user, role)
        UserSessionSettings.objects.create(
            user=user,
            inactivity_timeout_minutes=timeout,
            password_never_expires=never_expires,
        )
        return user

    def update(self, user, validated_data):
        role = validated_data.pop('role', None)
        password = validated_data.pop('password', None)
        timeout = validated_data.pop('inactivity_timeout_minutes', None)
        never_expires = validated_data.pop('password_never_expires', None)
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
        if never_expires is not None:
            settings.password_never_expires = never_expires
        if password:
            settings.password_changed_at = timezone.now()
        settings.save()
        return user

    def _assign_role(self, user, role):
        user.groups.set([Group.objects.get_or_create(name=role)[0]])
