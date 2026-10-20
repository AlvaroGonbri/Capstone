from django.urls import path

from .views import (
    AsignarView,
    CancelarView,
    CerrarView,
    IniciarView,
    IntervencionDetailView,
    IntervencionListView,
    TecnicosView,
)


urlpatterns = [
    path('', IntervencionListView.as_view(), name='intervencion_list'),
    path('tecnicos/', TecnicosView.as_view(), name='intervencion_tecnicos'),
    path('<int:pk>/', IntervencionDetailView.as_view(), name='intervencion_detail'),
    path('<int:pk>/asignar/', AsignarView.as_view(), name='intervencion_asignar'),
    path('<int:pk>/iniciar/', IniciarView.as_view(), name='intervencion_iniciar'),
    path('<int:pk>/cerrar/', CerrarView.as_view(), name='intervencion_cerrar'),
    path('<int:pk>/cancelar/', CancelarView.as_view(), name='intervencion_cancelar'),
]
