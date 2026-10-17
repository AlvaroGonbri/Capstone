from django.urls import path

from .views import (
    ActivoDetailView,
    ActivoHistorialView,
    ActivoListView,
    ResponsablesPosiblesView,
    TipoActivoDetailView,
    TipoActivoListView,
)


urlpatterns = [
    path('', ActivoListView.as_view(), name='activo_list'),
    path('<int:pk>/', ActivoDetailView.as_view(), name='activo_detail'),
    path('<int:pk>/historial/', ActivoHistorialView.as_view(), name='activo_historial'),
    path('tipos/', TipoActivoListView.as_view(), name='tipo_activo_list'),
    path('tipos/<int:pk>/', TipoActivoDetailView.as_view(), name='tipo_activo_detail'),
    path('responsables/', ResponsablesPosiblesView.as_view(), name='activo_responsables'),
]
