from django.conf import settings
from django.db import models
from django.utils import timezone


class UserSessionSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='session_settings',
    )
    inactivity_timeout_minutes = models.PositiveSmallIntegerField(default=15)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    password_never_expires = models.BooleanField(default=False)
    # RNF-SEG-02: intentos fallidos seguidos y hasta cuándo queda bloqueada la cuenta.
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'configuración de sesión'
        verbose_name_plural = 'configuraciones de sesión'

    def __str__(self):
        return f'{self.user} ({self.inactivity_timeout_minutes} min)'


class PasswordPolicy(models.Model):
    """Política global de contraseñas. Hay una sola fila (id=1)."""

    # 0 = las contraseñas no expiran.
    max_age_days = models.PositiveSmallIntegerField(default=90)

    class Meta:
        verbose_name = 'política de contraseñas'
        verbose_name_plural = 'política de contraseñas'

    def __str__(self):
        return f'Vigencia máxima: {self.max_age_days or "sin expiración"} días'

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]
