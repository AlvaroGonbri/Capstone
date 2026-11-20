"""Sesiones iniciadas: registro, actividad y revocación (pantalla "Sesiones activas").

Cada inicio de sesión (contraseña o huella) crea una SesionUsuario cuyo id es el jti de su refresh
token. Los tokens llevan ese id en el claim "sid": al revocar, el refresh token pasa a la lista
negra y la API rechaza también los access tokens de esa sesión en la siguiente petición.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import SesionUsuario
from .throttling import ORIGENES_DEL_TUNEL

CLAIM_SESION = 'sid'
INACTIVIDAD_POR_DEFECTO_MIN = 15


def ip_cliente(request) -> str:
    """IP real: detrás del túnel de Cloudflare viene en CF-Connecting-IP (igual que el límite de intentos)."""
    if request is None:
        return ''
    remoto = request.META.get('REMOTE_ADDR', '')
    if remoto in ORIGENES_DEL_TUNEL:
        return request.META.get('HTTP_CF_CONNECTING_IP', '').strip() or remoto
    return remoto


def describir_dispositivo(agente: str) -> str:
    """Resumen legible del User-Agent: 'Chrome · Windows', 'App SICMA · Android'."""
    a = agente or ''
    if not a:
        return ''
    if 'Android' in a:
        sistema = 'Android'
    elif 'iPhone' in a or 'iPad' in a:
        sistema = 'iOS'
    elif 'Windows' in a:
        sistema = 'Windows'
    elif 'Mac OS' in a:
        sistema = 'macOS'
    elif 'Linux' in a:
        sistema = 'Linux'
    else:
        sistema = ''
    if '; wv)' in a:
        navegador = 'App SICMA'  # WebView de Android: la app móvil
    elif 'Edg/' in a:
        navegador = 'Edge'
    elif 'OPR/' in a:
        navegador = 'Opera'
    elif 'Firefox/' in a:
        navegador = 'Firefox'
    elif 'Chrome/' in a:
        navegador = 'Chrome'
    elif 'Safari/' in a:
        navegador = 'Safari'
    else:
        navegador = 'Otro'
    return ' · '.join(p for p in (navegador, sistema) if p)[:120]


def registrar(request, usuario, refresh, canal: str, llave=None) -> SesionUsuario:
    return SesionUsuario.objects.create(
        id=refresh['jti'],
        usuario=usuario,
        canal=canal,
        ip=ip_cliente(request)[:45],
        dispositivo=describir_dispositivo(request.META.get('HTTP_USER_AGENT', '') if request else ''),
        vence=datetime.fromtimestamp(refresh['exp'], dt_timezone.utc),
        llave_jti=llave['jti'] if llave is not None else '',
    )


def esta_revocada(sid) -> bool:
    """Los tokens emitidos antes de que existiera el registro (sin fila) siguen valiendo."""
    return bool(sid) and SesionUsuario.objects.filter(pk=sid, motivo_cierre=SesionUsuario.CIERRE_REVOCADA).exists()


def marcar_actividad(sid) -> None:
    if sid:
        SesionUsuario.objects.filter(pk=sid, cerrada_en__isnull=True).update(ultima_actividad=timezone.now())


def _a_lista_negra(jti: str) -> None:
    token = OutstandingToken.objects.filter(jti=jti).first()
    if token is not None:
        BlacklistedToken.objects.get_or_create(token=token)


def cerrar(sesion: SesionUsuario, motivo: str) -> None:
    """Cierra la sesión. Revocada: además invalida su refresh token y, si es de la app, su huella."""
    if sesion.cerrada_en is not None:
        return
    sesion.cerrada_en = timezone.now()
    sesion.motivo_cierre = motivo
    sesion.save(update_fields=['cerrada_en', 'motivo_cierre'])
    if motivo == SesionUsuario.CIERRE_REVOCADA:
        _a_lista_negra(sesion.id)
        if sesion.llave_jti:
            _a_lista_negra(sesion.llave_jti)


def activas() -> list[SesionUsuario]:
    """Abiertas, sin vencer y dentro del tiempo de inactividad de su usuario."""
    ahora = timezone.now()
    sesiones = (
        SesionUsuario.objects.filter(cerrada_en__isnull=True, vence__gt=ahora, usuario__is_active=True)
        .select_related('usuario', 'usuario__session_settings')
        .order_by('-ultima_actividad')
    )
    vigentes = []
    for sesion in sesiones:
        ajustes = getattr(sesion.usuario, 'session_settings', None)
        minutos = ajustes.inactivity_timeout_minutes if ajustes else INACTIVIDAD_POR_DEFECTO_MIN
        if ahora - sesion.ultima_actividad <= timedelta(minutes=minutos):
            vigentes.append(sesion)
    return vigentes
