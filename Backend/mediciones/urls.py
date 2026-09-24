from django.urls import path

from .views import MedicionIngestView


urlpatterns = [
    path('', MedicionIngestView.as_view(), name='medicion_ingest'),
]
