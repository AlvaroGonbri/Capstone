"""Alertas ambientales (RF-AMB-04) y su aviso por correo (RF-AMB-05)."""
import logging
import threading
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import close_old_connections, transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from mediciones.models import UmbralAmbiental

from .models import ESTADOS_ABIERTOS, Alerta, Notificacion, ReglaAlerta


logger = logging.getLogger(__name__)

VARIABLES = (('Temperatura', 'temperatura', '°C'), ('Humedad', 'humedad', '%'))


def umbrales_vigentes(ubicacion_id):
    """{'Temperatura': (min, max), 'Humedad': (min, max)} con la última versión de cada variable."""
    ultima = UmbralAmbiental.objects.filter(
        ubicacion_id=ubicacion_id,
        variable=OuterRef('variable'),
    ).order_by('-version', '-vigente_desde', '-id').values('id')[:1]
    return {
        u.variable: (u.valor_minimo, u.valor_maximo)
        for u in UmbralAmbiental.objects.filter(id=Subquery(ultima), ubicacion_id=ubicacion_id)
    }


def evaluar_medicion(medicion):
    """Compara una lectura nueva con los umbrales de su zona.

    - Fuera de rango sin alerta abierta: crea una alerta y avisa por correo.
    - Fuera de rango con alerta abierta: suma una ocurrencia a esa alerta (RN-05), sin correo.
    - De vuelta en rango: cierra la alerta abierta. Una nueva salida abre otra (RN-04).
    """
    sensor = medicion.sensor
    umbrales = umbrales_vigentes(sensor.ubicacion_id)
    if not umbrales:
        return []

    ahora = timezone.now()
    nuevas = []
    with transaction.atomic():
        for variable, campo, unidad in VARIABLES:
            valor = getattr(medicion, campo)
            if valor is None or variable not in umbrales:
                continue
            minimo, maximo = umbrales[variable]
            abierta = (
                Alerta.objects.select_for_update()
                .filter(
                    origen='IoT',
                    sensor=sensor,
                    estado__in=ESTADOS_ABIERTOS,
                    condicion__startswith=f'{variable} fuera de rango',
                )
                .order_by('-id')
                .first()
            )
            if minimo <= valor <= maximo:
                if abierta:
                    abierta.estado = 'Cerrada'
                    abierta.save(update_fields=['estado'])
                continue

            condicion = (
                f'{variable} fuera de rango en {nombre_zona(sensor.ubicacion)}: '
                f'{valor} {unidad} (rango {minimo}–{maximo} {unidad})'
            )
            if abierta:
                abierta.contador_ocurrencias += 1
                abierta.fecha_ultima_ocurrencia = ahora
                abierta.condicion = condicion
                abierta.save(update_fields=['contador_ocurrencias', 'fecha_ultima_ocurrencia', 'condicion'])
            else:
                nuevas.append(Alerta.objects.create(
                    origen='IoT',
                    condicion=condicion,
                    severidad='Critica',
                    estado='Nueva',
                    fecha_apertura=ahora,
                    contador_ocurrencias=1,
                    fecha_ultima_ocurrencia=ahora,
                    sensor=sensor,
                ))

        for alerta in nuevas:
            transaction.on_commit(lambda alerta_id=alerta.id: programar_notificacion(alerta_id))
    return nuevas


def nombre_zona(ubicacion):
    return ' · '.join(filter(None, (ubicacion.sala, ubicacion.zona, ubicacion.rack)))


def responsables_zona(ubicacion_id):
    regla = (
        ReglaAlerta.objects.filter(fuente='IoT', condicion=ReglaAlerta.condicion_zona(ubicacion_id))
        .order_by('-version', '-id')
        .first()
    )
    return list(regla.destinatarios or []) if regla else []


def programar_notificacion(alerta_id):
    """Envía el correo fuera de la petición del sensor, para no demorar la ingesta (≤ 5 s)."""
    if getattr(settings, 'ALERTAS_CORREO_ASINCRONO', True):
        threading.Thread(target=_notificar_en_hilo, args=(alerta_id,), daemon=True).start()
    else:
        notificar_alerta(alerta_id)


def _notificar_en_hilo(alerta_id):
    try:
        notificar_alerta(alerta_id)
    except Exception:
        logger.exception('No fue posible notificar la alerta %s', alerta_id)
    finally:
        close_old_connections()


SEVERIDAD_TEXTO = {'Informativa': 'informativa', 'Advertencia': 'de advertencia', 'Alta': 'alta', 'Critica': 'crítica'}


def responsable_activo(activo_id):
    from inventario.models import Activo

    activo = Activo.objects.select_related('responsable').filter(pk=activo_id).first()
    responsable = activo.responsable if activo else None
    if responsable and responsable.is_active and responsable.email:
        return activo, [responsable.email]
    return activo, []


def _destinatarios_y_detalle(alerta):
    """Zona del sensor (alertas IoT) o responsable del activo vinculado (alertas Zabbix, RF-CAT-05)."""
    if alerta.sensor_id:
        return (
            responsables_zona(alerta.sensor.ubicacion_id),
            'SICMA detectó una lectura fuera de rango.',
            f'Sensor: {alerta.sensor.codigo}',
        )
    problema = alerta.host_problema_zabbix
    if problema and problema.activo_id:
        activo, destinatarios = responsable_activo(problema.activo_id)
        return (
            destinatarios,
            'Zabbix informó un problema en un activo a su cargo.',
            f'Activo: {activo.codigo} · {activo.nombre} (evento Zabbix {problema.identificador_externo})',
        )
    return [], '', ''


def notificar_alerta(alerta_id):
    """Envía la alerta a sus responsables y registra cada envío en `notificacion`."""
    alerta = Alerta.objects.select_related('sensor', 'host_problema_zabbix').get(pk=alerta_id)
    destinatarios, introduccion, origen = _destinatarios_y_detalle(alerta)
    if not destinatarios:
        logger.warning('La alerta %s no tiene responsables a quienes avisar', alerta.id)
        return []

    hora_local = alerta.fecha_apertura.astimezone(ZoneInfo(settings.SICMA_ZONA_HORARIA))
    asunto = f'[SICMA] Alerta {SEVERIDAD_TEXTO.get(alerta.severidad, "")}: {alerta.condicion[:120]}'
    cuerpo = (
        f'{introduccion}\n\n'
        f'{alerta.condicion}\n'
        f'{origen}\n'
        f'Fecha: {hora_local:%d-%m-%Y %H:%M:%S} ({settings.SICMA_ZONA_HORARIA})\n'
        f'Alerta N° {alerta.id}\n\n'
        f'Mientras la alerta siga abierta no se enviarán más correos por esta condición.\n'
        f'Este es un mensaje automático de SICMA; no responda a este correo.'
    )

    registros = []
    conexion = get_connection(fail_silently=False)
    for correo in destinatarios:
        try:
            EmailMessage(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [correo], connection=conexion).send()
            resultado = 'Enviado'
        except Exception:
            logger.exception('Falló el envío de la alerta %s a %s', alerta.id, correo)
            resultado = 'Fallido'
        registros.append(Notificacion.objects.create(
            alerta=alerta,
            canal='SMTP',
            destinatario=correo,
            fecha_envio=timezone.now(),
            resultado=resultado,
        ))
    return registros
