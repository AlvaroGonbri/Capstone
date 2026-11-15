"""Estado de todas las integraciones para la vista Integraciones (GET /api/sistema/integraciones/).

Solo informa si cada una está configurada y funcionando: nunca devuelve secretos ni sus hashes.
"""
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from accesos.models import PuntoAcceso
from infraestructura.models import EstadoInfraestructura
from infraestructura.sincronizacion import ANTIGUEDAD_MAXIMA
from mediciones.serializers import CONEXION_EN_LINEA, CONEXION_INACTIVO, SensorReadSerializer
from mediciones.views import SensorQuerysetMixin

from . import actividad, secretos
from .pruebas import sin_datos_internos


PROCESOS = (
    ('sincronizar_zabbix', 'Sincronización de Zabbix'),
    ('procesar_intervenciones', 'Lectura del buzón de intervenciones'),
)
INTERVALO_POR_DEFECTO = 60
# El agente del lector consulta a SICMA cada 5 s; el contacto se registra cada 30 s.
LECTOR_EN_LINEA = timedelta(minutes=2)


def _mas_reciente(*fechas):
    fechas = [f for f in fechas if f]
    return max(fechas) if fechas else None


def _error_vigente(act) -> str | None:
    """El último error, si es posterior a la última pasada buena."""
    if not act or not act.fecha_error or not act.ultimo_error:
        return None
    if act.ultimo_exito and act.ultimo_exito > act.fecha_error:
        return None
    return sin_datos_internos(act.ultimo_error)[:500]


def _proceso(clave: str, nombre: str, act) -> dict:
    intervalo = (act.intervalo_segundos if act else None) or INTERVALO_POR_DEFECTO
    ultima = act.ultima_actividad if act else None
    return {
        'clave': clave,
        'nombre': nombre,
        'ultima_actividad': ultima,
        'intervalo_segundos': intervalo,
        # Tres pasadas sin señales (más un margen): el proceso está detenido.
        'activo': bool(ultima) and timezone.now() - ultima <= timedelta(seconds=3 * intervalo + 30),
        'error': _error_vigente(act),
    }


def _enmascarar(correo: str | None) -> str | None:
    if not correo or '@' not in correo:
        return None
    usuario, dominio = correo.split('@', 1)
    return f'{usuario[:2]}•••@{dominio}'


def _sensores() -> dict:
    conexion = SensorReadSerializer().get_conexion
    resumen = {'en_linea': 0, 'sin_datos': 0, 'inactivos': 0}
    for sensor in SensorQuerysetMixin().sensor_queryset():
        estado = conexion(sensor)
        clave = 'en_linea' if estado == CONEXION_EN_LINEA else 'inactivos' if estado == CONEXION_INACTIVO else 'sin_datos'
        resumen[clave] += 1
    return resumen


def _lectores() -> list[dict]:
    puntos = list(PuntoAcceso.objects.order_by('nombre'))
    contactos = actividad.obtener(*(actividad.clave_lector(p.id) for p in puntos))
    ahora = timezone.now()
    lista = []
    for punto in puntos:
        act = contactos.get(actividad.clave_lector(punto.id))
        ultimo = act.ultimo_exito if act else None
        lista.append({
            'id': punto.id,
            'nombre': punto.nombre,
            'estado': punto.estado,
            'ultimo_contacto': ultimo,
            'en_linea': bool(ultimo) and ahora - ultimo <= LECTOR_EN_LINEA,
        })
    return lista


def estado_general(*, red_local: bool, puede_renovar: bool) -> dict:
    claves_procesos = [actividad.clave_proceso(c) for c, _ in PROCESOS]
    act = actividad.obtener(actividad.WEBHOOK_ZABBIX, actividad.CORREOS_FLUJO, 'gemini', *claves_procesos)
    ia = act.get('gemini')
    procesos = {c: _proceso(c, nombre, act.get(actividad.clave_proceso(c))) for c, nombre in PROCESOS}

    foto = EstadoInfraestructura.objects.filter(pk=1).first()
    ultima_zabbix = foto.ultima_exitosa if foto else None
    webhook = act.get(actividad.WEBHOOK_ZABBIX)
    correos = act.get(actividad.CORREOS_FLUJO)
    correo_configurado = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    url_publica = getattr(settings, 'URL_PUBLICA_API', '') or ''

    return {
        'generado': timezone.now(),
        'red_local': red_local,
        'puede_renovar': puede_renovar,
        'gracia_horas': int(secretos.GRACIA.total_seconds() // 3600),
        'zabbix': {
            'configurado': bool(getattr(settings, 'ZABBIX_URL', '') and getattr(settings, 'ZABBIX_TOKEN', '')),
            'ultimo_intento': foto.ultimo_intento if foto else None,
            'ultima_exitosa': ultima_zabbix,
            'al_dia': bool(ultima_zabbix) and timezone.now() - ultima_zabbix <= ANTIGUEDAD_MAXIMA,
            'error': sin_datos_internos(foto.error)[:500] if foto and foto.error else None,
        },
        'webhook': {
            'secreto': secretos.estado(secretos.WEBHOOK_ZABBIX),
            'ultimo_aviso': _mas_reciente(webhook and webhook.ultimo_exito, foto and foto.ultimo_webhook),
            'rechazos': webhook.rechazos if webhook else 0,
            'ultimo_rechazo': webhook.ultimo_rechazo if webhook else None,
        },
        'correo': {
            'configurado': correo_configurado,
            'cuenta': _enmascarar(settings.EMAIL_HOST_USER),
        },
        'buzon': {
            'configurado': bool(
                getattr(settings, 'INTERVENCIONES_CORREO_FLUJO', '')
                and correo_configurado
                and secretos.configurado(secretos.FLUJO_INTERVENCIONES)
            ),
            'secreto': secretos.estado(secretos.FLUJO_INTERVENCIONES),
            'proceso': procesos['procesar_intervenciones'],
            'ultimo_correo': correos.ultimo_exito if correos else None,
            'descartados': correos.rechazos if correos else 0,
            'ultimo_descarte': correos.ultimo_rechazo if correos else None,
            'detalle_descarte': sin_datos_internos(correos.detalle_rechazo) if correos and correos.detalle_rechazo else None,
        },
        'tunel': {'host': urlsplit(url_publica).hostname if url_publica else None},
        'gemini': {
            'configurado': bool(getattr(settings, 'GEMINI_API_KEY', '')),
            'modelo': getattr(settings, 'GEMINI_MODELO', '') or None,
            'ultimo_resumen': ia.ultimo_exito if ia else None,
            'error': _error_vigente(ia),
        },
        'procesos': list(procesos.values()),
        'sensores': _sensores(),
        'lectores': _lectores(),
        'renovaciones': secretos.renovaciones_recientes(),
    }
