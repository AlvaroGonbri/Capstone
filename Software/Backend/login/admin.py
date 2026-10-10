from django.contrib import admin

from .models import UserSessionSettings


@admin.register(UserSessionSettings)
class UserSessionSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'inactivity_timeout_minutes')
    list_filter = ('inactivity_timeout_minutes',)
