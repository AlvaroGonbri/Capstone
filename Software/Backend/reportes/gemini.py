"""Cliente mínimo de la API de Google Gemini (nivel gratuito), por HTTP con `requests`.

Es la misma API que usa el SDK google-genai, sin sumar dependencias. La clave se lee de GEMINI_API_KEY
(.env) y viaja en la cabecera x-goog-api-key, nunca en la URL. En el nivel gratuito Google puede usar lo
que se envía para mejorar sus productos: aquí solo se envían cifras agregadas (ver resumen.py).

Google retira modelos con el tiempo (responde 404). El modelo se cambia con GEMINI_MODELO en el .env, sin
tocar el código; el listado vigente está en aistudio.google.com.
"""
from django.conf import settings

import requests


URL = 'https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent'
MODELO_POR_DEFECTO = 'gemini-3.5-flash'
TIEMPO_MAXIMO = 20
# Si el modelo no acepta el nivel mínimo de razonamiento, se reintenta con "low"; lo que razona cuenta
# dentro de maxOutputTokens, así que se le da margen para que igual quede espacio para el texto.
MARGEN_RAZONAMIENTO = 2048


class GeminiNoDisponible(Exception):
    """Falta la clave, Gemini no respondió o rechazó la solicitud. El mensaje se puede mostrar."""


def configurado() -> bool:
    return bool(getattr(settings, 'GEMINI_API_KEY', ''))


def modelo() -> str:
    return getattr(settings, 'GEMINI_MODELO', '') or MODELO_POR_DEFECTO


def _razonamiento(nombre: str) -> dict | None:
    """El menor razonamiento que acepta cada generación: más rápido y gasta menos cupo."""
    if 'gemini-2.' in nombre:
        # 2.5 Flash se apaga con presupuesto 0; 2.5 Pro no permite apagarlo y no acepta el parámetro en 0.
        return {'thinkingBudget': 0} if 'flash' in nombre else None
    return {'thinkingLevel': 'minimal'}


def _mensaje_de_google(respuesta) -> str:
    try:
        return str(respuesta.json()['error']['message'])
    except (ValueError, KeyError, TypeError):
        return ''


def _enviar(nombre: str, cuerpo: dict):
    try:
        return requests.post(
            URL.format(modelo=nombre),
            headers={'x-goog-api-key': settings.GEMINI_API_KEY, 'Content-Type': 'application/json'},
            json=cuerpo,
            timeout=TIEMPO_MAXIMO,
        )
    except requests.Timeout as error:
        raise GeminiNoDisponible('Gemini no respondió a tiempo.') from error
    except requests.RequestException as error:
        raise GeminiNoDisponible('No fue posible conectar con Gemini.') from error


def generar(texto: str, instrucciones: str = '', max_tokens: int = 1024) -> str:
    if not configurado():
        raise GeminiNoDisponible('Falta GEMINI_API_KEY en el .env.')
    nombre = modelo()
    configuracion = {'temperature': 0.2, 'maxOutputTokens': max_tokens}
    razonamiento = _razonamiento(nombre)
    if razonamiento:
        configuracion['thinkingConfig'] = razonamiento
    cuerpo = {'contents': [{'role': 'user', 'parts': [{'text': texto}]}], 'generationConfig': configuracion}
    if instrucciones:
        cuerpo['systemInstruction'] = {'parts': [{'text': instrucciones}]}

    respuesta = _enviar(nombre, cuerpo)
    if (respuesta.status_code == 400 and razonamiento and 'thinkingLevel' in razonamiento
            and 'thinking' in _mensaje_de_google(respuesta).lower()):
        cuerpo = {**cuerpo, 'generationConfig': {**configuracion, 'thinkingConfig': {'thinkingLevel': 'low'},
                                                 'maxOutputTokens': max_tokens + MARGEN_RAZONAMIENTO}}
        respuesta = _enviar(nombre, cuerpo)

    if respuesta.status_code == 429:
        raise GeminiNoDisponible('Se alcanzó el límite del nivel gratuito de Gemini.')
    if respuesta.status_code == 404:
        raise GeminiNoDisponible(
            f'Google ya no ofrece el modelo {nombre} (HTTP 404): cambia GEMINI_MODELO en el .env y reinicia la API.'
        )
    if respuesta.status_code in (400, 401, 403):
        raise GeminiNoDisponible(f'Gemini rechazó la solicitud (HTTP {respuesta.status_code}): revisa la clave y el modelo.')
    if respuesta.status_code in (500, 502, 503, 504):
        raise GeminiNoDisponible(f'Gemini está saturado o con problemas (HTTP {respuesta.status_code}); se reintentará en unos minutos.')
    if respuesta.status_code >= 300:
        raise GeminiNoDisponible(f'Gemini respondió con error HTTP {respuesta.status_code}.')
    try:
        partes = respuesta.json()['candidates'][0]['content']['parts']
        resultado = ''.join(p.get('text', '') for p in partes if not p.get('thought')).strip()
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise GeminiNoDisponible('Gemini respondió sin texto.') from error
    if not resultado:
        raise GeminiNoDisponible('Gemini respondió sin texto.')
    return resultado
