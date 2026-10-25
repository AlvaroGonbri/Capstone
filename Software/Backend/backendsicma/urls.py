"""
URL configuration for backendsicma project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from infraestructura.views import ZabbixWebhookView
from mediciones.views import (
    SensorClaveView,
    SensorDetailView,
    SensorListView,
    UbicacionDetailView,
    UbicacionListView,
    UmbralListView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('login.urls')),
    path('api/mediciones/', include('mediciones.urls')),
    path('api/sensores/', SensorListView.as_view(), name='sensor_list'),
    path('api/sensores/<int:pk>/', SensorDetailView.as_view(), name='sensor_detail'),
    path('api/sensores/<int:pk>/clave/', SensorClaveView.as_view(), name='sensor_clave'),
    path('api/ubicaciones/', UbicacionListView.as_view(), name='ubicacion_list'),
    path('api/ubicaciones/<int:pk>/', UbicacionDetailView.as_view(), name='ubicacion_detail'),
    path('api/activos/', include('inventario.urls')),
    path('api/umbrales/', UmbralListView.as_view(), name='umbral_list'),
    path('api/infraestructura/', include('infraestructura.urls')),
    path('api/alertas/', include('alertas.urls')),
    path('api/intervenciones/', include('intervenciones.urls')),
    path('api/accesos/', include('accesos.urls')),
    path('api/integraciones/zabbix/webhook/', ZabbixWebhookView.as_view(), name='zabbix_webhook'),
]
