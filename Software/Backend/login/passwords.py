"""Vencimiento de contraseñas (RF-ID-03): política global y excepción por usuario."""
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from .models import PasswordPolicy, UserSessionSettings


class PasswordExpired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'La contraseña expiró. Debe cambiarla para continuar.'
    default_code = 'password_expired'

    def __init__(self):
        # Con un dict, DRF responde {'detail': ..., 'code': ...} y el frontend reconoce el caso.
        super().__init__({'detail': self.default_detail, 'code': self.default_code})


def password_expires_at(user, policy=None):
    """Fecha de vencimiento de la contraseña, o None si no expira."""
    session_settings = UserSessionSettings.objects.get_or_create(user=user)[0]
    if session_settings.password_never_expires:
        return None
    max_age_days = (policy or PasswordPolicy.get_solo()).max_age_days
    if not max_age_days:
        return None
    return session_settings.password_changed_at + timedelta(days=max_age_days)


def password_is_expired(user, policy=None):
    expires_at = password_expires_at(user, policy)
    return expires_at is not None and timezone.now() >= expires_at


def mark_password_changed(user):
    UserSessionSettings.objects.update_or_create(
        user=user,
        defaults={'password_changed_at': timezone.now()},
    )
