"""Comprobaciones reales de las integraciones (botones "Probar" de la vista Integraciones).

Dicen si funciona y por qué no, sin devolver secretos, URLs internas ni direcciones IP. El
resultado se guarda unos segundos: varios clics seguidos no vuelven a conectarse a Gmail o Zabbix.
"""
import imaplib
import re
import smtplib
import ssl
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

import requests

from infraestructura.zabbix_client import ZabbixClient, ZabbixError


CACHE_SEGUNDOS = 15
TIEMPO_MAXIMO = 8

# Rutas que el túnel debe bloquear (config.yml de cloudflared). Todas existen en SICMA y ante un
# GET responden 401/405; un 404 significa que las cortó Cloudflare.
RUTAS_BLOQUEADAS = ('/integraciones/zabbix/webhook/', '/accesos/lector/intentos/', '/mediciones/')


def sin_datos_internos(texto: str) -> str:
    """Quita URLs e IPs de un mensaje de error antes de mostrarlo."""
    texto = re.sub(r'https?://\S+', '[URL]', texto or '')
    return re.sub(r'\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b', '[IP]', texto)


def _resultado(ok: bool, detalle: str, **extra) -> dict:
    return {'ok': ok, 'detalle': detalle, 'probado_en': timezone.now(), **extra}


# ------------------------------------------------------------------ Zabbix

def probar_zabbix() -> dict:
    inicio = time.monotonic()
    try:
        cliente = ZabbixClient(timeout=TIEMPO_MAXIMO)
        version = cliente.version()
        cliente.verificar_token()
    except ZabbixError as error:
        texto = str(error)
        if 'rechazó' in texto:
            detalle = texto.split(':', 1)[-1].strip()
            return _resultado(False, f'Zabbix rechazó el token ({sin_datos_internos(detalle)}). '
                                     'Puede estar vencido, revocado o sin permisos.')
        return _resultado(False, sin_datos_internos(texto))
    except requests.Timeout:
        return _resultado(False, 'Zabbix no respondió a tiempo.')
    except requests.HTTPError as error:
        codigo = error.response.status_code if error.response is not None else '?'
        return _resultado(False, f'Zabbix respondió con error HTTP {codigo}.')
    except (requests.RequestException, ValueError):
        return _resultado(False, 'No fue posible conectar con Zabbix.')
    ms = round((time.monotonic() - inicio) * 1000)
    return _resultado(True, f'Zabbix {version} respondió y aceptó el token ({ms} ms).')


# ------------------------------------------------------------------ Correo (Gmail)

def _probar_smtp(usuario: str, clave: str) -> dict:
    try:
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=TIEMPO_MAXIMO) as smtp:
            if settings.EMAIL_USE_TLS:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(usuario, clave)
    except smtplib.SMTPAuthenticationError:
        return {'ok': False, 'detalle': 'Gmail rechazó la cuenta o la contraseña de aplicación para enviar.'}
    except TimeoutError:
        return {'ok': False, 'detalle': 'El servidor de envío no respondió a tiempo.'}
    except (smtplib.SMTPException, OSError):
        return {'ok': False, 'detalle': 'No fue posible conectar con el servidor de envío.'}
    return {'ok': True, 'detalle': 'Envío: Gmail aceptó la cuenta.'}


def _probar_imap(usuario: str, clave: str) -> dict:
    host = getattr(settings, 'INTERVENCIONES_IMAP_HOST', 'imap.gmail.com')
    try:
        with imaplib.IMAP4_SSL(host, timeout=TIEMPO_MAXIMO) as imap:
            imap.login(usuario, clave)
    except imaplib.IMAP4.error:
        return {'ok': False, 'detalle': 'Gmail rechazó la cuenta o la contraseña de aplicación para leer el buzón.'}
    except TimeoutError:
        return {'ok': False, 'detalle': 'El servidor de lectura no respondió a tiempo.'}
    except OSError:
        return {'ok': False, 'detalle': 'No fue posible conectar con el servidor de lectura.'}
    return {'ok': True, 'detalle': 'Lectura: Gmail aceptó la cuenta.'}


def probar_correo() -> dict:
    """Inicia sesión para enviar (SMTP) y para leer el buzón (IMAP). No envía ningún correo."""
    usuario, clave = settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD
    if not usuario or not clave:
        return _resultado(False, 'Faltan EMAIL_HOST_USER o EMAIL_HOST_PASSWORD.', envio=None, lectura=None)
    envio = _probar_smtp(usuario, clave)
    lectura = _probar_imap(usuario, clave)
    if envio['ok'] and lectura['ok']:
        return _resultado(True, 'Gmail aceptó la cuenta para enviar y para leer el buzón.', envio=envio, lectura=lectura)
    fallas = ' '.join(r['detalle'] for r in (envio, lectura) if not r['ok'])
    return _resultado(False, fallas, envio=envio, lectura=lectura)


# ------------------------------------------------------------------ Túnel de Cloudflare

def probar_tunel() -> dict:
    """SICMA se consulta a sí mismo por la URL pública: confirma que el túnel llega de punta a
    punta y que las rutas internas siguen bloqueadas desde internet."""
    base = (getattr(settings, 'URL_PUBLICA_API', '') or '').rstrip('/')
    if not base:
        return _resultado(False, 'Falta URL_PUBLICA_API en la configuración.', expuestas=[])
    partes = urlsplit(base)
    host = partes.hostname or base
    try:
        # Sin credenciales: SICMA responde 401 a /auth/me/.
        respuesta = requests.get(f'{base}/auth/me/', timeout=TIEMPO_MAXIMO)
    except requests.Timeout:
        return _resultado(False, f'{host} no respondió a tiempo.', expuestas=[])
    except requests.RequestException:
        return _resultado(False, f'No fue posible conectar con {host}.', expuestas=[])
    if 'cf-ray' not in respuesta.headers:
        return _resultado(False, f'{host} no está respondiendo a través de Cloudflare.', expuestas=[])
    if respuesta.status_code != 401:
        return _resultado(
            False,
            f'Cloudflare responde, pero el túnel no llega a SICMA (HTTP {respuesta.status_code}). '
            'Revisa que el servicio cloudflared esté iniciado.',
            expuestas=[],
        )

    expuestas = []
    for ruta in RUTAS_BLOQUEADAS:
        try:
            if requests.get(f'{base}{ruta}', timeout=TIEMPO_MAXIMO).status_code != 404:
                expuestas.append(f'{partes.path}{ruta}')
        except requests.RequestException:
            continue
    if expuestas:
        return _resultado(
            False,
            'El túnel responde, pero publica en internet rutas que deberían estar bloqueadas: '
            f"{', '.join(expuestas)}. Revisa config.yml de cloudflared.",
            expuestas=expuestas,
        )
    return _resultado(True, f'{host} responde a través del túnel y las rutas internas siguen bloqueadas.', expuestas=[])


# ------------------------------------------------------------------ Gemini (resumen de Reportes)

def probar_gemini() -> dict:
    """Pide una respuesta mínima: confirma la clave, el modelo y que quede cupo gratuito."""
    from reportes import gemini

    if not gemini.configurado():
        return _resultado(False, 'Falta GEMINI_API_KEY en el .env: Reportes usa el resumen de plantilla.')
    inicio = time.monotonic()
    try:
        gemini.generar('Responde solo con la palabra: funciona', max_tokens=16)
    except gemini.GeminiNoDisponible as error:
        return _resultado(False, str(error))
    ms = round((time.monotonic() - inicio) * 1000)
    return _resultado(True, f'Gemini ({gemini.modelo()}) respondió ({ms} ms).')


PRUEBAS = {'zabbix': probar_zabbix, 'correo': probar_correo, 'tunel': probar_tunel, 'gemini': probar_gemini}


def probar(nombre: str) -> dict:
    clave = f'integraciones:prueba:{nombre}'
    resultado = cache.get(clave)
    if resultado is None:
        resultado = PRUEBAS[nombre]()
        cache.set(clave, resultado, CACHE_SEGUNDOS)
    return resultado
