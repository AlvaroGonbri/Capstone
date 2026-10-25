from django.urls import path

from .views import AlertaListView, CerrarAlertaView, ReconocerAlertaView, ResponsablesListView, ResponsablesZonaView


urlpatterns = [
    path('', AlertaListView.as_view(), name='alerta_list'),
    path('<int:pk>/reconocer/', ReconocerAlertaView.as_view(), name='alerta_reconocer'),
    path('<int:pk>/cerrar/', CerrarAlertaView.as_view(), name='alerta_cerrar'),
    path('responsables/', ResponsablesListView.as_view(), name='alerta_responsables'),
    path('responsables/<int:ubicacion_id>/', ResponsablesZonaView.as_view(), name='alerta_responsables_zona'),
]
