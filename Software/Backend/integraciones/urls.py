from django.urls import path

from .views import EstadoIntegracionesView, ProbarIntegracionView


# Montadas en /api/sistema/integraciones/ (publicadas por el túnel). La renovación de secretos va
# aparte, en /api/integraciones/secretos/ (ver backendsicma/urls.py), que el túnel no publica.
urlpatterns = [
    path('', EstadoIntegracionesView.as_view(), name='integraciones_estado'),
    path('<str:nombre>/probar/', ProbarIntegracionView.as_view(), name='integraciones_probar'),
]
