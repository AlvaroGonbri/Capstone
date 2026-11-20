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


class SesionUsuario(models.Model):
    """Una sesión iniciada (web o app móvil): la ven y la pueden revocar los administradores.

    El id es el jti del refresh token de la sesión; los access tokens lo llevan en el claim "sid",
    así que una sesión revocada deja de funcionar en la siguiente petición, sin esperar a que venza.
    """

    CANAL_WEB = 'web'
    CANAL_MOVIL = 'movil'
    CIERRE_SALIDA = 'salida'      # la persona cerró sesión
    CIERRE_REVOCADA = 'revocada'  # la cerró un administrador

    id = models.CharField(primary_key=True, max_length=64)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sesiones')
    canal = models.CharField(max_length=10, default=CANAL_WEB)
    ip = models.CharField(max_length=45, blank=True, default='')
    dispositivo = models.CharField(max_length=120, blank=True, default='')
    inicio = models.DateTimeField(default=timezone.now)
    ultima_actividad = models.DateTimeField(default=timezone.now)
    vence = models.DateTimeField()
    # App móvil: jti de la llave del dispositivo emitida con esta sesión (para apagar la huella al revocar).
    llave_jti = models.CharField(max_length=64, blank=True, default='')
    cerrada_en = models.DateTimeField(null=True, blank=True)
    motivo_cierre = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        verbose_name = 'sesión'
        verbose_name_plural = 'sesiones'
        indexes = [models.Index(fields=['cerrada_en', 'vence'])]

    def __str__(self):
        return f'{self.usuario} · {self.canal} · {self.inicio:%Y-%m-%d %H:%M}'
