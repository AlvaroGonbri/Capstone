from django.urls import path

from .views import PdfReporteView, ResumenReporteView


urlpatterns = [
    path('resumen/', ResumenReporteView.as_view(), name='reportes_resumen'),
    path('pdf/', PdfReporteView.as_view(), name='reportes_pdf'),
]
