"""Decisión de acceso y registro del intento (RF-ACC-01).

El agente del lector informa qué identificador reconoció (o que no reconoció ninguno). SICMA
decide con lo que tiene registrado: persona activa, permiso vigente para ese punto y, si el
permiso tiene ventanas horarias, que el intento caiga dentro de una. Así revocar un permiso en
SICMA tiene efecto inmediato sin tocar el PC del lector.
"""
from dataclasses import dataclass
from datetime import timedelta
import re
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    ACTIVO,
    BAJA_COMPLETADA,
    BAJA_FALLIDA,
    BAJA_PENDIENTE,
    DENEGADO,
    DIAS_SEMANA,
    ENROL_ABIERTAS,
    ENROL_CANCELADA,
    ENROL_COMPLETADA,
    ENROL_EN_CURSO,
    ENROL_FALLIDA,
    ENROL_PENDIENTE,
    ERROR,
    INACTIVO,
    PERMITIDO,
    BajaHuella,
    CambioHabilitacion,
    EventoAcceso,
    PermisoAcceso,
    PersonaAutorizada,
    PuntoAcceso,
    SolicitudEnrolamiento,
    SolicitudVerificacion,
)

# Lo que informa el agente.
COINCIDE = 'coincide'
SIN_COINCIDENCIA = 'sin_coincidencia'
FALLA_LECTOR = 'error'
IDENTIFICADOR_DESCONOCIDO = 'desconocido'


@dataclass
class Decision:
    resultado: str
    motivo: str
    persona: PersonaAutorizada | None = None


def _dentro_de_ventana(dia, momento):
    hora = momento.time()
    if dia.hora_inicio <= dia.hora_fin:
        return dia.hora_inicio <= hora <= dia.hora_fin
    return hora >= dia.hora_inicio or hora <= dia.hora_fin  # ventana que cruza la medianoche


def decidir(punto, estado_lector, identificador, fecha_hora):
    if estado_lector == FALLA_LECTOR:
        return Decision(ERROR, 'Falla del lector')
    if estado_lector == SIN_COINCIDENCIA:
        return Decision(DENEGADO, 'Huella no reconocida')

    persona = PersonaAutorizada.objects.filter(identificador_biometrico_externo=identificador).first()
    if persona is None:
        return Decision(DENEGADO, 'Identificador no registrado en SICMA')
    if persona.estado != ACTIVO:
        return Decision(DENEGADO, 'Persona desactivada', persona)

    local = fecha_hora.astimezone(ZoneInfo(settings.SICMA_ZONA_HORARIA))
    permisos = list(
        persona.permisos.filter(punto_acceso=punto, estado=ACTIVO, vigencia_inicio__lte=local.date())
        .filter(Q(vigencia_fin__isnull=True) | Q(vigencia_fin__gte=local.date()))
        .prefetch_related('dias')
    )
    if not permisos:
        return Decision(DENEGADO, 'Sin permiso vigente para este punto', persona)
    dia_semana = DIAS_SEMANA[local.weekday()]
    for permiso in permisos:
        ventanas = list(permiso.dias.all())
        if not ventanas or any(v.dia_semana == dia_semana and _dentro_de_ventana(v, local) for v in ventanas):
            return Decision(PERMITIDO, 'Acceso autorizado', persona)
    return Decision(DENEGADO, 'Fuera del horario autorizado', persona)


def registrar_intento(punto, evento_id, estado_lector, identificador, fecha_hora, motivo_lector=''):
    """Decide y guarda el intento. Un reintento del agente con el mismo evento_id no se duplica."""
    existente = EventoAcceso.objects.filter(punto_acceso=punto, evento_externo_id=evento_id).select_related('persona').first()
    if existente:
        return existente, False
    decision = decidir(punto, estado_lector, identificador, fecha_hora)
    motivo = decision.motivo
    if decision.resultado == ERROR and motivo_lector:
        motivo = f'{motivo}: {motivo_lector}'
    try:
        with transaction.atomic():
            evento = EventoAcceso.objects.create(
                identificador_biometrico_externo=identificador or IDENTIFICADOR_DESCONOCIDO,
                persona=decision.persona,
                punto_acceso=punto,
                fecha_hora=fecha_hora,
                resultado=decision.resultado,
                motivo=motivo[:255],
                evento_externo_id=evento_id,
            )
    except IntegrityError:  # dos reintentos simultáneos: gana el primero
        return EventoAcceso.objects.get(punto_acceso=punto, evento_externo_id=evento_id), False
    return evento, True


# ------------------------------------------------------------ personal externo

# Una solicitud que nadie atiende o un agente que deja de responder no deben quedar abiertos para siempre.
VENCE_PENDIENTE = timedelta(minutes=15)
VENCE_EN_CURSO = timedelta(minutes=3)


def normalizar_rut(texto):
    """'12.345.678-k' → '12345678-K'. Lanza ValueError si el dígito verificador no corresponde."""
    limpio = re.sub(r'[.\s-]', '', (texto or '').upper())
    if not re.fullmatch(r'\d{7,8}[\dK]', limpio):
        raise ValueError('El RUT debe tener 7 u 8 dígitos y su dígito verificador, por ejemplo 12.345.678-5.')
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma = sum(int(d) * f for d, f in zip(reversed(cuerpo), [2, 3, 4, 5, 6, 7] * 2))
    esperado = {10: 'K', 11: '0'}.get(11 - suma % 11, str(11 - suma % 11))
    if dv != esperado:
        raise ValueError('El dígito verificador del RUT no es válido.')
    return f'{cuerpo}-{dv}'


def crear_persona(datos):
    """Alta del personal externo. Sin identificador explícito, SICMA genera EXT-00001."""
    with transaction.atomic():
        identificador = datos.pop('identificador_biometrico_externo', '') or f'TMP-{timezone.now().timestamp()}'
        persona = PersonaAutorizada.objects.create(identificador_biometrico_externo=identificador, **datos)
        if identificador.startswith('TMP-'):
            persona.identificador_biometrico_externo = f'EXT-{persona.id:05d}'
            persona.save(update_fields=['identificador_biometrico_externo'])
    return persona


def cambiar_habilitacion(persona, habilitada, motivo, usuario):
    """Alta o baja manual (p. ej. cotizaciones al día). Queda en el historial con quién, cuándo y por qué."""
    with transaction.atomic():
        persona.estado = ACTIVO if habilitada else INACTIVO
        persona.save(update_fields=['estado'])
        return CambioHabilitacion.objects.create(
            persona=persona, habilitada=habilitada, motivo=motivo, usuario=usuario, fecha_hora=timezone.now(),
        )


def _vencer_solicitudes():
    ahora = timezone.now()
    for modelo in (SolicitudEnrolamiento, SolicitudVerificacion):
        _vencer(modelo, ahora)


def _vencer(modelo, ahora):
    modelo.objects.filter(estado=ENROL_PENDIENTE, fecha_solicitud__lt=ahora - VENCE_PENDIENTE).update(
        estado=ENROL_FALLIDA, mensaje='Ningún lector tomó la solicitud a tiempo.', fecha_fin=ahora,
    )
    modelo.objects.filter(estado=ENROL_EN_CURSO, fecha_inicio__lt=ahora - VENCE_EN_CURSO).update(
        estado=ENROL_FALLIDA, mensaje='El lector no informó el resultado a tiempo.', fecha_fin=ahora,
    )


def solicitar_enrolamiento(persona, punto, usuario):
    """Pide al agente del lector que capture la huella. Reemplaza cualquier solicitud abierta de la persona."""
    with transaction.atomic():
        SolicitudEnrolamiento.objects.filter(persona=persona, estado__in=ENROL_ABIERTAS).update(
            estado=ENROL_CANCELADA, mensaje='Reemplazada por una solicitud nueva.', fecha_fin=timezone.now(),
        )
        return SolicitudEnrolamiento.objects.create(
            persona=persona, punto_acceso=punto, solicitada_por=usuario, fecha_solicitud=timezone.now(),
        )


def tomar_enrolamiento(punto):
    """El agente pide trabajo: entrega la solicitud pendiente más antigua de su lector y la marca en curso."""
    _vencer_solicitudes()
    with transaction.atomic():
        solicitud = (
            SolicitudEnrolamiento.objects.select_for_update().select_related('persona')
            .filter(punto_acceso=punto, estado=ENROL_PENDIENTE).order_by('id').first()
        )
        if solicitud:
            solicitud.estado, solicitud.fecha_inicio = ENROL_EN_CURSO, timezone.now()
            solicitud.save(update_fields=['estado', 'fecha_inicio'])
    return solicitud


def informar_enrolamiento(solicitud, exito, mensaje):
    with transaction.atomic():
        solicitud.estado = ENROL_COMPLETADA if exito else ENROL_FALLIDA
        solicitud.mensaje, solicitud.fecha_fin = mensaje[:255], timezone.now()
        solicitud.save(update_fields=['estado', 'mensaje', 'fecha_fin'])
        if exito:
            persona = solicitud.persona
            persona.huella_registrada_en, persona.huella_registrada_por = solicitud.fecha_fin, solicitud.solicitada_por
            persona.save(update_fields=['huella_registrada_en', 'huella_registrada_por'])
    return solicitud


def eliminar_persona(persona, usuario):
    """Borra a la persona de SICMA y ordena a los lectores borrar su huella.

    Los intentos de acceso se conservan (el script del equipo lo exige: persona_id queda en NULL) con su
    identificador; los permisos, el historial de habilitación y las solicitudes de enrolamiento se borran.
    Devuelve cuántos lectores recibieron la orden de borrar la huella.
    """
    with transaction.atomic():
        # Todo lector activo, más los que alguna vez la enrolaron aunque hoy estén inactivos.
        puntos = set(PuntoAcceso.objects.filter(estado=ACTIVO).values_list('id', flat=True))
        puntos |= set(persona.enrolamientos.filter(estado=ENROL_COMPLETADA).values_list('punto_acceso_id', flat=True))
        ahora = timezone.now()
        BajaHuella.objects.bulk_create([
            BajaHuella(
                punto_acceso_id=punto, identificador=persona.identificador_biometrico_externo, nombre=persona.nombre[:150],
                solicitada_por=usuario, fecha_solicitud=ahora,
            )
            for punto in sorted(puntos)
        ])
        EventoAcceso.objects.filter(persona=persona).update(persona=None)
        for permiso in PermisoAcceso.objects.filter(persona=persona):
            permiso.dias.all().delete()
            permiso.delete()
        persona.cambios_habilitacion.all().delete()
        persona.enrolamientos.all().delete()
        persona.delete()
    return len(puntos)


def tomar_baja(punto):
    return BajaHuella.objects.filter(punto_acceso=punto, estado=BAJA_PENDIENTE).first()


def informar_baja(baja, exito, mensaje):
    baja.estado = BAJA_COMPLETADA if exito else BAJA_FALLIDA
    baja.mensaje, baja.fecha_fin = mensaje[:255], timezone.now()
    baja.save(update_fields=['estado', 'mensaje', 'fecha_fin'])
    return baja


# ---------------------------------------------------- verificación de identidad

def solicitar_verificacion(persona, punto, intervencion_id, usuario):
    with transaction.atomic():
        SolicitudVerificacion.objects.filter(persona=persona, intervencion_id=intervencion_id, estado__in=ENROL_ABIERTAS).update(
            estado=ENROL_CANCELADA, mensaje='Reemplazada por una solicitud nueva.', fecha_fin=timezone.now(),
        )
        return SolicitudVerificacion.objects.create(
            persona=persona, punto_acceso=punto, intervencion_id=intervencion_id, solicitada_por=usuario,
            fecha_solicitud=timezone.now(),
        )


def tomar_verificacion(punto):
    _vencer_solicitudes()
    with transaction.atomic():
        solicitud = (
            SolicitudVerificacion.objects.select_for_update().select_related('persona')
            .filter(punto_acceso=punto, estado=ENROL_PENDIENTE).order_by('id').first()
        )
        if solicitud:
            solicitud.estado, solicitud.fecha_inicio = ENROL_EN_CURSO, timezone.now()
            solicitud.save(update_fields=['estado', 'fecha_inicio'])
    return solicitud


def informar_verificacion(solicitud, coincide, identificado, mensaje):
    """Cierra la verificación y la deja en el registro de accesos (RF-ACC-01)."""
    persona = solicitud.persona
    habilitada = persona.estado == ACTIVO
    exito = coincide and habilitada
    if coincide and not habilitada:
        mensaje = 'La huella coincide, pero la persona está deshabilitada.'
    motivo = f'Verificación de identidad · intervención #{solicitud.intervencion_id}: {mensaje}'
    with transaction.atomic():
        solicitud.estado = ENROL_COMPLETADA if exito else ENROL_FALLIDA
        solicitud.identificado, solicitud.mensaje, solicitud.fecha_fin = identificado or '', mensaje[:255], timezone.now()
        solicitud.save(update_fields=['estado', 'identificado', 'mensaje', 'fecha_fin'])
        otra = None if coincide or not identificado else PersonaAutorizada.objects.filter(identificador_biometrico_externo=identificado).first()
        EventoAcceso.objects.create(
            identificador_biometrico_externo=identificado or IDENTIFICADOR_DESCONOCIDO,
            persona=persona if coincide else otra,
            punto_acceso=solicitud.punto_acceso,
            fecha_hora=solicitud.fecha_fin,
            resultado=PERMITIDO if exito else DENEGADO,
            motivo=motivo[:255],
            evento_externo_id=f'verificacion-{solicitud.id}',
        )
        if exito and solicitud.intervencion_id:
            from intervenciones.servicio import marcar_verificada  # evita la importación circular

            marcar_verificada(solicitud.intervencion_id, persona, solicitud.solicitada_por)
    return solicitud
