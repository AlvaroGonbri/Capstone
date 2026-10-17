from django.urls import path

from .views import AlertaListView, ResponsablesListView, ResponsablesZonaView


urlpatterns = [
    path('', AlertaListView.as_view(), name='alerta_list'),
    path('responsables/', ResponsablesListView.as_view(), name='alerta_responsables'),
    path('responsables/<int:ubicacion_id>/', ResponsablesZonaView.as_view(), name='alerta_responsables_zona'),
]
