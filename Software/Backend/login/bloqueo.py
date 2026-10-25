"""Bloqueo de cuenta tras intentos fallidos (RNF-SEG-02).

Tras LOGIN_MAX_INTENTOS contraseñas incorrectas seguidas, la cuenta queda bloqueada
LOGIN_BLOQUEO_MINUTOS, aunque luego se escriba la contraseña correcta. Un ingreso exitoso
reinicia el contador. Complementa el límite por IP (throttling): este protege cada cuenta
aunque el atacante cambie de IP.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from .models import UserSessionSettings


class CuentaBloqueada(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = 'account_locked'

    def __init__(self, hasta):
        hora = timezone.localtime(hasta).strftime('%H:%M')
        super().__init__({
            'detail': f'La cuenta está bloqueada por intentos fallidos. Vuelve a intentarlo después de las {hora}.',
            'code': self.default_code,
        })


def _ajustes(usuario):
    return UserSessionSettings.objects.get_or_create(user=usuario)[0]


def comprobar(usuario):
    ajustes = _ajustes(usuario)
    if ajustes.locked_until and ajustes.locked_until > timezone.now():
        raise CuentaBloqueada(ajustes.locked_until)


def registrar_fallo(usuario):
    ajustes = _ajustes(usuario)
    ajustes.failed_login_attempts += 1
    if ajustes.failed_login_attempts >= settings.LOGIN_MAX_INTENTOS:
        ajustes.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_BLOQUEO_MINUTOS)
        ajustes.failed_login_attempts = 0
    ajustes.save(update_fields=['failed_login_attempts', 'locked_until'])


def registrar_exito(usuario):
    UserSessionSettings.objects.filter(user=usuario).update(failed_login_attempts=0, locked_until=None)
