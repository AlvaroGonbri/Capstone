from django.urls import path

from .views import (
    AsignarView,
    CancelarView,
    CerrarView,
    IniciarView,
    IntervencionDetailView,
    IntervencionListView,
    PersonalView,
    TecnicosView,
    VerificarPersonalView,
)


urlpatterns = [
    path('', IntervencionListView.as_view(), name='intervencion_list'),
    path('tecnicos/', TecnicosView.as_view(), name='intervencion_tecnicos'),
    path('<int:pk>/', IntervencionDetailView.as_view(), name='intervencion_detail'),
    path('<int:pk>/asignar/', AsignarView.as_view(), name='intervencion_asignar'),
    path('<int:pk>/personal/', PersonalView.as_view(), name='intervencion_personal'),
    path('<int:pk>/personal/<int:persona_id>/verificar/', VerificarPersonalView.as_view(), name='intervencion_verificar'),
    path('<int:pk>/iniciar/', IniciarView.as_view(), name='intervencion_iniciar'),
    path('<int:pk>/cerrar/', CerrarView.as_view(), name='intervencion_cerrar'),
    path('<int:pk>/cancelar/', CancelarView.as_view(), name='intervencion_cancelar'),
]
