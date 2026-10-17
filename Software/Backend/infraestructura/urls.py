from django.urls import path

from .views import (
    ActivosZabbixView,
    InfraestructuraEstadoView,
    InfraestructuraEventosHostView,
    InfraestructuraHostsView,
)


urlpatterns = [
    path('activos/', ActivosZabbixView.as_view(), name='infraestructura_activos'),
    path('estado/', InfraestructuraEstadoView.as_view(), name='infraestructura_estado'),
    path('hosts/', InfraestructuraHostsView.as_view(), name='infraestructura_hosts'),
    path('hosts/<int:hostid>/eventos/', InfraestructuraEventosHostView.as_view(), name='infraestructura_eventos_host'),
]
