"""Ciclo de vida de una intervención (RF-INT-02 a RF-INT-06) y sus avisos por correo.

Pendiente --(Jefatura en Teams)--> Aprobada | Rechazada
Aprobada  --(Administrador asigna técnico y horario)--> Aprobada + correo AGENDAR al flujo
Aprobada  --(técnico inicia)--> EnEjecucion --(técnico cierra)--> Ejecutada | Fallida
Pendiente | Aprobada --(Administrador)--> Cancelada
"""
from datetime import timedelta, timezone as dt_timezone
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
    IntervencionPersona,
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


# El personal externo puede entrar desde un poco antes del inicio; verificar su huella, desde 1 hora antes.
MARGEN_PERMISO = timedelta(minutes=30)
MARGEN_VERIFICACION = timedelta(hours=1)


def _revocar_permisos(ip):
    from accesos.models import REVOCADO, PermisoAcceso

    if ip.permisos:
        PermisoAcceso.objects.filter(id__in=ip.permisos).update(estado=REVOCADO)
        ip.permisos = []
        ip.save(update_fields=['permisos'])


def _crear_permisos(ip, intervencion):
    """Permiso en cada lector activo, solo para el día y el horario de la intervención."""
    from accesos.models import ACTIVO, DIAS_SEMANA, PermisoAcceso, PermisoDia, PuntoAcceso

    desde = timezone.localtime(intervencion.fecha_inicio - MARGEN_PERMISO, _zona())
    hasta = timezone.localtime(intervencion.fecha_termino, _zona())
    ids = []
    for punto in PuntoAcceso.objects.filter(estado=ACTIVO):
        permiso = PermisoAcceso.objects.create(
            persona=ip.persona, punto_acceso=punto, vigencia_inicio=desde.date(), vigencia_fin=hasta.date(), estado=ACTIVO,
        )
        if desde.date() == hasta.date():  # varios días: vale el día completo dentro de la vigencia
            PermisoDia.objects.create(
                permiso=permiso, dia_semana=DIAS_SEMANA[desde.weekday()], hora_inicio=desde.time().replace(microsecond=0),
                hora_fin=hasta.time().replace(microsecond=0),
            )
        ids.append(permiso.id)
    ip.permisos = ids
    ip.save(update_fields=['permisos'])


def sincronizar_permisos(intervencion):
    """Rehace los permisos del personal según el horario actual (al asignar o al cambiar el personal)."""
    if not (intervencion.fecha_inicio and intervencion.fecha_termino):
        return
    for ip in intervencion.personal_externo.select_related('persona'):
        _revocar_permisos(ip)
        _crear_permisos(ip, intervencion)


def revocar_permisos_personal(intervencion):
    for ip in intervencion.personal_externo.all():
        _revocar_permisos(ip)


def fijar_personal(intervencion, personas, usuario):
    """Reemplaza el personal externo de la intervención. Solo mientras no se haya iniciado."""
    _exigir_estado(intervencion, PENDIENTE, APROBADA)
    ids = {p.id for p in personas}
    for ip in IntervencionPersona.objects.filter(intervencion=intervencion).exclude(persona_id__in=ids):
        _revocar_permisos(ip)
        ip.delete()
    existentes = set(intervencion.personal_externo.values_list('persona_id', flat=True))
    IntervencionPersona.objects.bulk_create([
        IntervencionPersona(intervencion=intervencion, persona=p, agregada_por=usuario, fecha=timezone.now())
        for p in personas if p.id not in existentes
    ])
    sincronizar_permisos(intervencion)


def solicitar_verificacion(intervencion, persona, punto, usuario):
    """El técnico pide que la persona apoye su huella para demostrar que es quien fue asignada."""
    from accesos import servicio as accesos

    _exigir_estado(intervencion, APROBADA)
    if not intervencion.personal_externo.filter(persona=persona).exists():
        raise TransicionInvalida(f'{persona.nombre} no está asignada a esta intervención.')
    ahora = timezone.now()
    if not intervencion.fecha_inicio or not intervencion.fecha_termino:
        raise TransicionInvalida('La intervención aún no tiene horario.')
    if ahora < intervencion.fecha_inicio - MARGEN_VERIFICACION or ahora > intervencion.fecha_termino:
        raise TransicionInvalida(
            f'La huella se verifica desde 1 hora antes del inicio ({_hora_local(intervencion.fecha_inicio)}) '
            f'hasta el término ({_hora_local(intervencion.fecha_termino)}).'
        )
    return accesos.solicitar_verificacion(persona, punto, intervencion.id, usuario)


def marcar_verificada(intervencion_id, persona, usuario):
    IntervencionPersona.objects.filter(intervencion_id=intervencion_id, persona=persona).update(
        verificada_en=timezone.now(), verificada_por=usuario,
    )


def personal_pendiente(intervencion):
    """Quién impide iniciar: sin verificar su huella o deshabilitado después de verificarla."""
    from accesos.models import ACTIVO

    return [
        ip.persona.nombre + (' (deshabilitada)' if ip.persona.estado != ACTIVO else ' (sin verificar su huella)')
        for ip in intervencion.personal_externo.select_related('persona')
        if ip.verificada_en is None or ip.persona.estado != ACTIVO
    ]


def nombres_personal(intervencion):
    return ', '.join(
        f'{ip.persona.nombre} ({ip.persona.empresa or "sin empresa"})'
        for ip in intervencion.personal_externo.select_related('persona')
    )


def asignar(intervencion, tecnico, fecha_inicio, fecha_termino, activos, personal=None, usuario=None):
    """RF-INT-05: el Administrador asigna técnico, horario y personal externo; SICMA pide agendarla."""
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
        if personal is not None:
            fijar_personal(intervencion, personal, usuario)
        else:
            sincronizar_permisos(intervencion)  # el horario pudo cambiar
        programar_agenda(intervencion.id)
        programar_aviso(intervencion.id, f'Se asignó al técnico {_nombre(tecnico)}.')
    return intervencion


def iniciar(intervencion):
    """RF-INT-06: el técnico registra el inicio de la ejecución."""
    with transaction.atomic():
        _exigir_estado(intervencion, APROBADA)
        if not intervencion.responsable_id:
            raise TransicionInvalida('Primero el Administrador debe asignar un técnico.')
        pendientes = personal_pendiente(intervencion)
        if pendientes:
            raise TransicionInvalida('Falta verificar al personal externo: ' + ', '.join(pendientes) + '.')
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
        revocar_permisos_personal(intervencion)  # terminado el trabajo, el personal externo ya no entra
        programar_aviso(intervencion.id, f'Observación del cierre: {observacion}')
    return intervencion


def cancelar(intervencion, motivo):
    with transaction.atomic():
        _exigir_estado(intervencion, PENDIENTE, APROBADA)
        intervencion.estado = CANCELADA
        intervencion.fecha_cierre = timezone.now()
        intervencion.observacion_cierre = motivo
        intervencion.save(update_fields=['estado', 'fecha_cierre', 'observacion_cierre'])
        revocar_permisos_personal(intervencion)
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
        f'Personal externo: {nombres_personal(intervencion)}' if intervencion.personal_externo.exists() else None,
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
            f'Personal externo: {nombres_personal(intervencion) or "-"}\n'
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
