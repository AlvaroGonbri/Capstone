from django.conf import settings
from django.db import models


class UserSessionSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='session_settings',
    )
    inactivity_timeout_minutes = models.PositiveSmallIntegerField(default=15)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'configuración de sesión'
        verbose_name_plural = 'configuraciones de sesión'

    def __str__(self):
        return f'{self.user} ({self.inactivity_timeout_minutes} min)'
