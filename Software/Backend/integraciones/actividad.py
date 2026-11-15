"""Registro liviano de la actividad de cada integración (lo muestra la vista Integraciones).

Nunca interrumpe a quien lo llama: si la base de datos falla (p. ej. falta aplicar la migración),
el webhook, el buzón o el agente siguen funcionando y el problema queda en el log.
"""
import logging

from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import F
from django.utils import timezone

from .models import ActividadIntegracion


logger = logging.getLogger(__name__)

WEBHOOK_ZABBIX = 'webhook_zabbix'
CORREOS_FLUJO = 'correos_flujo'


def clave_proceso(nombre: str) -> str:
    return f'proceso:{nombre}'


def clave_lector(punto_id: int) -> str:
    return f'lector:{punto_id}'


def _guardar(clave: str, campos: dict, al_crear: dict | None = None) -> None:
    try:
        if not ActividadIntegracion.objects.filter(clave=clave).update(**campos):
            ActividadIntegracion.objects.get_or_create(clave=clave, defaults=al_crear or campos)
    except DatabaseError:
        logger.warning('No fue posible registrar la actividad de %s.', clave, exc_info=True)


def latido(clave: str, *, intervalo: int | None = None, error: object = None) -> None:
    """Un proceso periódico terminó una pasada (con o sin error)."""
    ahora = timezone.now()
    campos = {'ultima_actividad': ahora, 'intervalo_segundos': intervalo}
    if error is None:
        campos['ultimo_exito'] = ahora
    else:
        campos.update(ultimo_error=str(error)[:2000], fecha_error=ahora)
    _guardar(clave, campos)


def exito(clave: str) -> None:
    ahora = timezone.now()
    _guardar(clave, {'ultima_actividad': ahora, 'ultimo_exito': ahora})


def rechazo(clave: str, detalle: str = '') -> None:
    ahora = timezone.now()
    comunes = {'ultima_actividad': ahora, 'ultimo_rechazo': ahora, 'detalle_rechazo': detalle[:300]}
    _guardar(clave, {**comunes, 'rechazos': F('rechazos') + 1}, al_crear={**comunes, 'rechazos': 1})


def contacto(clave: str, cada_segundos: int = 30) -> None:
    """Para señales muy frecuentes (el agente del lector consulta cada 5 s): escribe a lo más
    una vez cada `cada_segundos`."""
    if cache.add(f'integraciones:contacto:{clave}', 1, cada_segundos):
        exito(clave)


def obtener(*claves: str) -> dict[str, ActividadIntegracion]:
    try:
        return {a.clave: a for a in ActividadIntegracion.objects.filter(clave__in=claves)}
    except DatabaseError:
        logger.warning('No fue posible leer la actividad de las integraciones.', exc_info=True)
        return {}
