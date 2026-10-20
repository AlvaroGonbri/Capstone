"""Ciclo de vida de una intervención (RF-INT-02 a RF-INT-06) y sus avisos por correo.

Pendiente --(Jefatura en Teams)--> Aprobada | Rechazada
Aprobada  --(Administrador asigna técnico y horario)--> Aprobada + correo AGENDAR al flujo
Aprobada  --(técnico inicia)--> EnEjecucion --(técnico cierra)--> Ejecutada | Fallida
Pendiente | Aprobada --(Administrador)--> Cancelada
"""
from datetime import timezone as dt_timezone
import json
import logging
import threading
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import close_old_connections, transaction
from django.utils import timezone

from alertas.models import Notificacion

from .models import (
    APROBADA,
    CANCELADA,
    EJECUTADA,
    EN_EJECUCION,
    FALLIDA,
    PENDIENTE,
    RECHAZADA,
    DecisionIntervencion,
    Intervencion,
    IntervencionActivo,
)


logger = logging.getLogger(__name__)

# Asunto que identifica los correos entre SICMA y el flujo de Power Automate.
ETIQUETA_ASUNTO = '[SICMA-INT]'

ETIQUETA_ESTADO = {
    PENDIENTE: 'recibida, pendiente de aprobación',
    APROBADA: 'aprobada',
    RECHAZADA: 'rechazada',
    EN_EJECUCION: 'en ejecución',
    EJECUTADA: 'ejecutada',
    FALLIDA: 'cerrada como fallida',
    CANCELADA: 'cancelada',
}


class TransicionInvalida(Exception):
    """La intervención no está en un estado que permita la operación."""


def _exigir_estado(intervencion, *estados):
    if intervencion.estado not in estados:
        raise TransicionInvalida(
            f'La intervención #{intervencion.id} está {ETIQUETA_ESTADO.get(intervencion.estado, intervencion.estado)}; '
            'no se puede realizar esta operación.'
        )


def _hora_local(fecha):
    return timezone.localtime(fecha, timezone=_zona()).strftime('%d/%m/%Y %H:%M') if fecha else 'por definir'


def _zona():
    return ZoneInfo(settings.SICMA_ZONA_HORARIA)


# ------------------------------------------------------------------ transiciones

def crear_desde_forms(forms_id, nombre, correo, rack, servicios, fecha_inicio, fecha_termino=None,
                      descripcion='', plan_reversa=''):
    """RF-INT-02: registra la solicitud con estado Pendiente. Idempotente por id de Forms."""
    with transaction.atomic():
        intervencion, creada = Intervencion.objects.get_or_create(
            origen_externo_id=forms_id,
            defaults={
                'objetivo': f'Intervención en {rack}'[:500],
                'descripcion': descripcion or f'Solicitud de {nombre} ({correo}) recibida desde Microsoft Forms.',
                'plan_reversa': plan_reversa or None,
                'impacto_esperado': servicios,
                'rack': rack[:200],
                'solicitante_nombre': nombre[:200],
                'solicitante_correo': correo[:254],
                'fecha_inicio': fecha_inicio,
                'fecha_termino': fecha_termino,
                'fecha_solicitud': timezone.now(),
                'estado': PENDIENTE,
            },
        )
        if creada:
            programar_aviso(intervencion.id, 'Recibimos la solicitud.')
    return intervencion, creada


def registrar_decision(forms_id, aprobada, decisor_correo, comentario):
    """RF-INT-03: la decisión de la Jefatura llega desde Teams. Las decisiones repetidas se ignoran."""
    from django.contrib.auth import get_user_model

    with transaction.atomic():
        intervencion = Intervencion.objects.select_for_update().filter(origen_externo_id=forms_id).first()
        if intervencion is None:
            raise TransicionInvalida(f'No existe una intervención para la respuesta de Forms {forms_id}.')
        if intervencion.estado != PENDIENTE:
            return intervencion, False
        decisor = get_user_model().objects.filter(email__iexact=decisor_correo, is_active=True).first() if decisor_correo else None
        estado = APROBADA if aprobada else RECHAZADA
        DecisionIntervencion.objects.create(
            intervencion=intervencion, decisor=decisor, decisor_correo=decisor_correo or None,
            decision=estado, observacion=comentario or None, fecha_hora=timezone.now(),
        )
        intervencion.estado = estado
        intervencion.save(update_fields=['estado'])
        programar_aviso(intervencion.id, 'La Jefatura registró su decisión.' + (f' Comentario: {comentario}' if comentario else ''))
    return intervencion, True


def asignar(intervencion, tecnico, fecha_inicio, fecha_termino, activos):
    """RF-INT-05: el Administrador asigna técnico y horario; SICMA pide al flujo agendarla en Outlook."""
    with transaction.atomic():
        _exigir_estado(intervencion, APROBADA)
        intervencion.responsable = tecnico
        intervencion.fecha_inicio = fecha_inicio
        intervencion.fecha_termino = fecha_termino
        intervencion.save(update_fields=['responsable', 'fecha_inicio', 'fecha_termino'])
        if activos is not None:
            IntervencionActivo.objects.filter(intervencion=intervencion).exclude(activo__in=activos).delete()
            existentes = set(intervencion.activos_afectados.values_list('activo_id', flat=True))
            IntervencionActivo.objects.bulk_create([
                IntervencionActivo(intervencion=intervencion, activo=activo)
                for activo in activos if activo.id not in existentes
            ])
        programar_agenda(intervencion.id)
        programar_aviso(intervencion.id, f'Se asignó al técnico {_nombre(tecnico)}.')
    return intervencion


def iniciar(intervencion):
    """RF-INT-06: el técnico registra el inicio de la ejecución."""
    with transaction.atomic():
        _exigir_estado(intervencion, APROBADA)
        if not intervencion.responsable_id:
            raise TransicionInvalida('Primero el Administrador debe asignar un técnico.')
        intervencion.estado = EN_EJECUCION
        intervencion.save(update_fields=['estado'])
        programar_aviso(intervencion.id, 'El técnico comenzó la intervención.')
    return intervencion


def cerrar(intervencion, exitosa, observacion):
    """RF-INT-06: el técnico registra el cierre (Ejecutada o Fallida) con su observación."""
    with transaction.atomic():
        _exigir_estado(intervencion, EN_EJECUCION)
        intervencion.estado = EJECUTADA if exitosa else FALLIDA
        intervencion.fecha_cierre = timezone.now()
        intervencion.observacion_cierre = observacion
        intervencion.save(update_fields=['estado', 'fecha_cierre', 'observacion_cierre'])
        programar_aviso(intervencion.id, f'Observación del cierre: {observacion}')
    return intervencion


def cancelar(intervencion, motivo):
    with transaction.atomic():
        _exigir_estado(intervencion, PENDIENTE, APROBADA)
        intervencion.estado = CANCELADA
        intervencion.fecha_cierre = timezone.now()
        intervencion.observacion_cierre = motivo
        intervencion.save(update_fields=['estado', 'fecha_cierre', 'observacion_cierre'])
        programar_aviso(intervencion.id, f'Motivo: {motivo}')
    return intervencion


# --------------------------------------------------------------------- correos

def _nombre(usuario):
    return (usuario.get_full_name() or usuario.get_username()) if usuario else 'sin asignar'


def _en_segundo_plano(funcion, *args):
    """Tras el commit: en hilo (peticiones web) o en línea (comandos periódicos y pruebas)."""
    def ejecutar():
        if getattr(settings, 'ALERTAS_CORREO_ASINCRONO', True):
            threading.Thread(target=_en_hilo, args=(funcion, *args), daemon=True).start()
        else:
            funcion(*args)
    transaction.on_commit(ejecutar)


def _en_hilo(funcion, *args):
    try:
        funcion(*args)
    except Exception:
        logger.exception('Falló el envío de correo de la intervención %s', args[0] if args else '')
    finally:
        close_old_connections()


def programar_aviso(intervencion_id, detalle=''):
    _en_segundo_plano(avisar_involucrados, intervencion_id, detalle)


def programar_agenda(intervencion_id):
    _en_segundo_plano(enviar_agenda, intervencion_id)


def _enviar(intervencion_id, canal, destinatario, asunto, cuerpo):
    try:
        EmailMessage(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [destinatario]).send()
        resultado = 'Enviado'
    except Exception:
        logger.exception('No fue posible enviar el correo de la intervención %s a %s', intervencion_id, destinatario)
        resultado = 'Fallido'
    Notificacion.objects.create(
        intervencion_id=intervencion_id, canal=canal, destinatario=destinatario,
        fecha_envio=timezone.now(), resultado=resultado,
    )
    return resultado == 'Enviado'


def avisar_involucrados(intervencion_id, detalle=''):
    """RF-INT-04: avisa el estado actual al solicitante (key user) y al técnico asignado."""
    intervencion = Intervencion.objects.select_related('responsable').get(pk=intervencion_id)
    destinatarios = {c.lower() for c in (intervencion.solicitante_correo, getattr(intervencion.responsable, 'email', None)) if c}
    if not destinatarios:
        return
    estado = ETIQUETA_ESTADO.get(intervencion.estado, intervencion.estado)
    asunto = f'SICMA · Intervención #{intervencion.id} {estado}'
    cuerpo = '\n'.join(filter(None, [
        f'La intervención #{intervencion.id} está {estado}.',
        detalle,
        '',
        f'Rack: {intervencion.rack or "-"}',
        f'Servicios afectados: {intervencion.impacto_esperado or "-"}',
        f'Descripción: {intervencion.descripcion}' if intervencion.descripcion else None,
        f'Inicio: {_hora_local(intervencion.fecha_inicio)}',
        f'Término: {_hora_local(intervencion.fecha_termino)}' if intervencion.fecha_termino else None,
        f'Técnico: {_nombre(intervencion.responsable)}',
        f'Solicitante: {intervencion.solicitante_nombre or "-"} ({intervencion.solicitante_correo or "-"})',
        '',
        'Mensaje automático de SICMA. No responda este correo.',
    ]))
    for destinatario in sorted(destinatarios):
        _enviar(intervencion_id, 'SMTP', destinatario, asunto, cuerpo)


def datos_agenda(intervencion):
    """Lo que el flujo necesita para crear la cita en el calendario de Outlook."""
    tecnico = intervencion.responsable
    return {
        'id': intervencion.id,
        'forms_id': intervencion.origen_externo_id,
        'titulo': f'Intervención #{intervencion.id} · {intervencion.rack or intervencion.objetivo}',
        # ISO 8601 en UTC: el flujo lo pasa tal cual a "Crear evento" con zona horaria UTC.
        'inicio': intervencion.fecha_inicio.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        'fin': intervencion.fecha_termino.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        'tecnico': _nombre(tecnico),
        'tecnico_correo': tecnico.email if tecnico else '',
        'solicitante_correo': intervencion.solicitante_correo or '',
        'rack': intervencion.rack or '',
        'servicios': intervencion.impacto_esperado or '',
        'detalle': (
            f'Rack: {intervencion.rack or "-"}\n'
            f'Servicios afectados: {intervencion.impacto_esperado or "-"}\n'
            f'Descripción: {intervencion.descripcion or "-"}\n'
            f'Plan de reversa: {intervencion.plan_reversa or "-"}\n'
            f'Técnico: {_nombre(tecnico)}\n'
            f'Solicitante: {intervencion.solicitante_nombre or "-"} ({intervencion.solicitante_correo or "-"})'
        ),
    }


def enviar_agenda(intervencion_id):
    """RF-INT-05: pide al flujo de Power Automate que cree la cita (correo con JSON en el cuerpo)."""
    destino = getattr(settings, 'INTERVENCIONES_CORREO_FLUJO', '')
    if not destino:
        logger.warning('INTERVENCIONES_CORREO_FLUJO no está configurado: la intervención %s no se agendó.', intervencion_id)
        return False
    intervencion = Intervencion.objects.select_related('responsable').get(pk=intervencion_id)
    asunto = f'{ETIQUETA_ASUNTO} AGENDAR #{intervencion.id}'
    return _enviar(intervencion_id, 'PowerAutomate', destino, asunto, json.dumps(datos_agenda(intervencion), ensure_ascii=False))
