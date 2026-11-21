"""Verificación en dos pasos con app de autenticación (TOTP, RFC 6238).

Google Authenticator, Microsoft Authenticator, Authy, etc. generan un código de 6 dígitos cada 30 s
a partir de un secreto compartido que se entrega una sola vez con un código QR.

Flujo del login cuando la cuenta la tiene exigida (UserSessionSettings.mfa_requerida):
  1. /api/auth/token/ valida la contraseña y, en vez de tokens, responde un "desafío":
     {"mfa": "codigo", "mfa_token": ...}            si ya la configuró, o
     {"mfa": "configurar", "mfa_token": ..., "qr", "secreto"}  si aún no (primera vez o restablecida).
  2. /api/auth/token/mfa/ recibe el mfa_token y el código; si es correcto entrega la sesión (y, al
     configurar, los códigos de respaldo, que se muestran una sola vez).

El mfa_token es una firma de Django que vence en 5 minutos y deja de servir si cambia la contraseña.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from django.core import signing
from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from rest_framework.exceptions import AuthenticationFailed

from .dispositivo import resumen_clave

EMISOR = 'SICMA'
PASO_SEGUNDOS = 30
DIGITOS = 6
VIGENCIA_DESAFIO_SEGUNDOS = 5 * 60
CODIGOS_RESPALDO = 8
_SAL = 'sicma.login.mfa'
_ALFABETO_RESPALDO = 'abcdefghjkmnpqrstuvwxyz23456789'  # sin 0/o, 1/l/i: se leen sin confundirse


# ------------------------------------------------------------------ TOTP

def nuevo_secreto() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def _hotp(secreto: str, contador: int) -> str:
    clave = base64.b32decode(secreto + '=' * (-len(secreto) % 8))
    resumen = hmac.new(clave, struct.pack('>Q', contador), hashlib.sha1).digest()
    desfase = resumen[-1] & 0x0F
    numero = (struct.unpack('>I', resumen[desfase:desfase + 4])[0] & 0x7FFFFFFF) % 10 ** DIGITOS
    return str(numero).zfill(DIGITOS)


def codigo_actual(secreto: str, ahora: float | None = None) -> str:
    """Solo para pruebas: el código que mostraría la app en este momento."""
    return _hotp(secreto, int((ahora if ahora is not None else time.time()) // PASO_SEGUNDOS))


def verificar_totp(secreto: str, codigo: str, ultimo_paso: int, ahora: float | None = None) -> int | None:
    """Intervalo aceptado o None. Tolera un intervalo de desfase del reloj del teléfono y no acepta
    un intervalo ya usado (un código interceptado no sirve una segunda vez)."""
    if not secreto or not codigo.isdigit() or len(codigo) != DIGITOS:
        return None
    actual = int((ahora if ahora is not None else time.time()) // PASO_SEGUNDOS)
    for paso in (actual - 1, actual, actual + 1):
        if paso > ultimo_paso and hmac.compare_digest(_hotp(secreto, paso), codigo):
            return paso
    return None


def uri(secreto: str, cuenta: str) -> str:
    return (f'otpauth://totp/{quote(EMISOR)}:{quote(cuenta)}?secret={secreto}'
            f'&issuer={quote(EMISOR)}&digits={DIGITOS}&period={PASO_SEGUNDOS}')


def qr_svg(texto: str, tamano: int = 220) -> str:
    """Código QR como imagen SVG en data URI (reportlab ya está instalado para los PDF de Reportes)."""
    widget = QrCodeWidget(texto)
    x0, y0, x1, y1 = widget.getBounds()
    dibujo = Drawing(tamano, tamano, transform=[tamano / (x1 - x0), 0, 0, tamano / (y1 - y0), 0, 0])
    dibujo.add(widget)
    return 'data:image/svg+xml;base64,' + base64.b64encode(renderSVG.drawToString(dibujo).encode()).decode()


# ------------------------------------------------------------------ códigos de respaldo

def _normalizar(codigo: str) -> str:
    return ''.join(c for c in codigo.lower() if c.isalnum())


def _resumen(codigo: str) -> str:
    return hashlib.sha256(_normalizar(codigo).encode()).hexdigest()


def nuevos_codigos_respaldo() -> tuple[list[str], list[str]]:
    """(códigos para mostrar una vez, sus resúmenes para guardar)."""
    planos = []
    for _ in range(CODIGOS_RESPALDO):
        crudo = ''.join(secrets.choice(_ALFABETO_RESPALDO) for _ in range(10))
        planos.append(f'{crudo[:5]}-{crudo[5:]}')
    return planos, [_resumen(c) for c in planos]


def usar_codigo_respaldo(ajustes, codigo: str) -> bool:
    """Si el código es uno de respaldo sin usar, lo gasta (un solo uso) y devuelve True."""
    resumen = _resumen(codigo)
    restantes = list(ajustes.mfa_codigos_respaldo or [])
    if not _normalizar(codigo) or resumen not in restantes:
        return False
    restantes.remove(resumen)
    ajustes.mfa_codigos_respaldo = restantes
    ajustes.save(update_fields=['mfa_codigos_respaldo'])
    return True


# ------------------------------------------------------------------ desafío del login

def desafio(usuario, ajustes, canal: str) -> dict:
    """Respuesta del login con contraseña cuando la cuenta tiene exigida la verificación."""
    token = signing.dumps({'u': usuario.pk, 'c': canal, 'k': resumen_clave(usuario)}, salt=_SAL)
    if ajustes.mfa_activa:
        return {'mfa': 'codigo', 'mfa_token': token}
    # Primera vez o restablecida: se conserva el secreto pendiente si ya se había generado, por si la
    # persona alcanzó a escanearlo antes de cerrar la pantalla.
    if not ajustes.mfa_secreto:
        ajustes.mfa_secreto = nuevo_secreto()
        ajustes.save(update_fields=['mfa_secreto'])
    enlace = uri(ajustes.mfa_secreto, usuario.email or usuario.get_username())
    return {'mfa': 'configurar', 'mfa_token': token, 'secreto': ajustes.mfa_secreto, 'qr': qr_svg(enlace)}


def leer_desafio(token: str) -> dict:
    try:
        return signing.loads(token, salt=_SAL, max_age=VIGENCIA_DESAFIO_SEGUNDOS)
    except signing.BadSignature:  # incluye SignatureExpired
        raise AuthenticationFailed({
            'detail': 'La verificación venció. Vuelve a ingresar tu contraseña.', 'code': 'mfa_vencido',
        })
