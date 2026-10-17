"""Registro de los eventos técnicos que Zabbix envía por webhook (RF-INF-02)."""
from django.db import transaction
from django.utils import timezone

from inventario.models import Activo

from .models import ESTADOS_ABIERTOS, Alerta, HostProblemaZabbix
from .servicio import programar_notificacion


# Severidad de Zabbix ({EVENT.SEVERITY}, en inglés o español) -> escala de la tabla alerta.
SEVERIDAD_ALERTA = {
    'not classified': 'Informativa',
    'no clasificado': 'Informativa',
    'information': 'Informativa',
    'información': 'Informativa',
    'warning': 'Advertencia',
    'advertencia': 'Advertencia',
    'average': 'Alta',
    'media': 'Alta',
    'high': 'Alta',
    'alta': 'Alta',
    'disaster': 'Critica',
    'desastre': 'Critica',
}


def registrar_evento_zabbix(event_id, host, problema, severidad, estado):
    """Guarda un PROBLEM o RESOLVED de Zabbix y abre o cierra su alerta.

    Es idempotente: si Zabbix reintenta el envío, no se duplican filas ni alertas.
    Si el host coincide con el código de un activo del inventario, queda vinculado a él y la
    alerta nueva se avisa por correo a su responsable (RF-CAT-05).
    Devuelve la alerta asociada (None si el problema se resolvió antes de que SICMA lo conociera).
    """
    ahora = timezone.now()
    activo = Activo.objects.filter(codigo__iexact=host.strip()).only('id').first()
    with transaction.atomic():
        problema_zbx, _ = HostProblemaZabbix.objects.select_for_update().get_or_create(
            identificador_externo=str(event_id),
            defaults={'severidad': severidad, 'estado': estado, 'fecha_ultima_sincronizacion': ahora},
        )
        problema_zbx.severidad = severidad or problema_zbx.severidad
        problema_zbx.estado = estado
        problema_zbx.fecha_ultima_sincronizacion = ahora
        if activo and not problema_zbx.activo_id:
            problema_zbx.activo_id = activo.id
        problema_zbx.save(update_fields=['severidad', 'estado', 'fecha_ultima_sincronizacion', 'activo_id'])

        alerta = problema_zbx.alertas.order_by('-id').first()
        if estado == 'PROBLEM':
            if alerta is None:
                alerta = Alerta.objects.create(
                    origen='Zabbix',
                    condicion=f'{host}: {problema}'[:500],
                    severidad=SEVERIDAD_ALERTA.get((severidad or '').strip().lower(), 'Advertencia'),
                    estado='Nueva',
                    fecha_apertura=ahora,
                    contador_ocurrencias=1,
                    fecha_ultima_ocurrencia=ahora,
                    host_problema_zabbix=problema_zbx,
                )
                if problema_zbx.activo_id:
                    transaction.on_commit(lambda alerta_id=alerta.id: programar_notificacion(alerta_id))
            else:
                alerta.fecha_ultima_ocurrencia = ahora
                alerta.save(update_fields=['fecha_ultima_ocurrencia'])
        elif alerta is not None and alerta.estado in ESTADOS_ABIERTOS:
            alerta.estado = 'Cerrada'
            alerta.save(update_fields=['estado'])
    return alerta
