"""Datos de un reporte por período (GET /api/reportes/resumen/), a partir de las mismas tablas que
usan Panel, Monitoreo, Accesos e Intervenciones, y de las tendencias de Zabbix para la disponibilidad.

Las fechas del período son días completos en la hora de Chile (SICMA_ZONA_HORARIA).
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import Coalesce

import requests

from accesos.models import EventoAcceso
from alertas.models import ESTADOS_ABIERTOS, Alerta
from infraestructura.sincronizacion import GRUPOS_MONITOREADOS
from infraestructura.zabbix_client import ZabbixClient, ZabbixError
from intervenciones.models import ESTADOS_CERRADOS, Intervencion
from inventario.models import Activo
from mediciones.models import Medicion, Ubicacion


MAX_DIAS = 92
CACHE_DISPONIBILIDAD = 600  # las tendencias de Zabbix son por hora: no hace falta consultarlas a cada rato
SEVERIDADES_ALTAS = ('Alta', 'Critica')
EVENTOS_DESTACADOS = 8


def zona_horaria() -> ZoneInfo:
    return ZoneInfo(settings.SICMA_ZONA_HORARIA)


@dataclass(frozen=True)
class Periodo:
    desde: date
    hasta: date
    zona: Ubicacion | None = None

    @property
    def inicio(self) -> datetime:
        return datetime.combine(self.desde, time.min, tzinfo=zona_horaria())

    @property
    def fin(self) -> datetime:
        """Exclusivo: medianoche del día siguiente a `hasta`."""
        return datetime.combine(self.hasta + timedelta(days=1), time.min, tzinfo=zona_horaria())

    @property
    def dias(self) -> int:
        return (self.hasta - self.desde).days + 1


def nombre_ubicacion(u: Ubicacion) -> str:
    return ' · '.join(p for p in (u.sala, u.zona, u.rack, u.posicion) if p)


def ubicaciones_de(zona: Ubicacion) -> set[int]:
    """La zona y todo lo que cuelga de ella (ubicacion_padre), p. ej. una sala con sus racks."""
    ids, pendientes = {zona.id}, [zona.id]
    while pendientes:
        hijos = list(Ubicacion.objects.filter(ubicacion_padre_id__in=pendientes).values_list('id', flat=True))
        pendientes = [h for h in hijos if h not in ids]
        ids.update(pendientes)
    return ids


def _redondear(valor, decimales: int = 1):
    return None if valor is None else round(float(valor), decimales)


# ------------------------------------------------------------------ Disponibilidad (Zabbix)

def _fraccion_disponible(hora: dict) -> float | None:
    """Fracción de la hora en que el agente estuvo disponible (1 = disponible, 2 = no, 0 = desconocido)."""
    if hora['max'] <= 0:
        return None  # solo "desconocido": esa hora no cuenta
    if hora['min'] >= 1:
        return max(0.0, min(1.0, 2.0 - hora['avg']))
    return 1.0 if hora['max'] <= 1 else 0.0  # mezcla con "desconocido": se toma lo conocido


def _tendencias(periodo: Periodo) -> list[dict]:
    clave = f'reportes:disponibilidad:{periodo.desde}:{periodo.hasta}'
    datos = cache.get(clave)
    if datos is None:
        cliente = ZabbixClient(timeout=15)
        datos = cliente.disponibilidad_agentes(
            GRUPOS_MONITOREADOS, int(periodo.inicio.timestamp()), int(periodo.fin.timestamp()) - 1,
        )
        cache.set(clave, datos, CACHE_DISPONIBILIDAD)
    return datos


def disponibilidad(periodo: Periodo, ubicaciones: set[int] | None) -> dict:
    vacio = {'porcentaje': None, 'hosts': [], 'por_dia': [], 'error': None}
    hosts_de_zona = None
    if ubicaciones is not None:
        hosts_de_zona = {
            c.lower() for c in Activo.objects.filter(ubicacion_id__in=ubicaciones).values_list('codigo', flat=True)
        }
    try:
        tendencias = _tendencias(periodo)
    except (ZabbixError, requests.RequestException, ValueError):
        return {**vacio, 'error': 'Zabbix no respondió: la disponibilidad del período no está disponible.'}

    tz = zona_horaria()
    hosts, por_dia_host = [], {}
    for h in tendencias:
        if hosts_de_zona is not None and h['host'].lower() not in hosts_de_zona:
            continue
        fracciones = []
        for hora in h['horas']:
            f = _fraccion_disponible(hora)
            if f is None:
                continue
            fracciones.append(f)
            dia = datetime.fromtimestamp(hora['clock'], tz).date().isoformat()
            por_dia_host.setdefault(dia, {}).setdefault(h['host'], []).append(f)
        hosts.append({
            'host': h['host'],
            'porcentaje': _redondear(100 * sum(fracciones) / len(fracciones), 2) if fracciones else None,
            'horas_sin_disponibilidad': _redondear(sum(1 - f for f in fracciones)),
            'horas_con_datos': len(fracciones),
        })

    por_dia = []
    for i in range(periodo.dias):
        dia = (periodo.desde + timedelta(days=i)).isoformat()
        medias = [sum(v) / len(v) for v in por_dia_host.get(dia, {}).values() if v]
        por_dia.append({'fecha': dia, 'porcentaje': _redondear(100 * sum(medias) / len(medias), 2) if medias else None})

    con_datos = [h['porcentaje'] for h in hosts if h['porcentaje'] is not None]
    hosts.sort(key=lambda h: (h['porcentaje'] is None, h['porcentaje'] if h['porcentaje'] is not None else 0))
    return {
        'porcentaje': _redondear(sum(con_datos) / len(con_datos), 2) if con_datos else None,
        'hosts': hosts,
        'por_dia': por_dia,
        'error': None if hosts or hosts_de_zona is None else 'La zona elegida no tiene servidores inventariados.',
    }


# ------------------------------------------------------------------ Datos de SICMA

def _ambiente(periodo: Periodo, ubicaciones: set[int] | None) -> dict:
    # RN-06: las lecturas simuladas no se mezclan con las reales.
    lecturas = Medicion.objects.filter(
        origen='Real', fecha_hora_medicion__gte=periodo.inicio, fecha_hora_medicion__lt=periodo.fin,
    )
    if ubicaciones is not None:
        lecturas = lecturas.filter(sensor__ubicacion_id__in=ubicaciones)
    r = lecturas.aggregate(
        n=Count('id'),
        t_prom=Avg('temperatura'), t_min=Min('temperatura'), t_max=Max('temperatura'),
        h_prom=Avg('humedad'), h_min=Min('humedad'), h_max=Max('humedad'),
    )
    return {
        'lecturas': r['n'],
        'temperatura': {'promedio': _redondear(r['t_prom']), 'minimo': _redondear(r['t_min']), 'maximo': _redondear(r['t_max'])},
        'humedad': {'promedio': _redondear(r['h_prom']), 'minimo': _redondear(r['h_min']), 'maximo': _redondear(r['h_max'])},
    }


def _alertas(periodo: Periodo, origen: str, ubicaciones: set[int] | None):
    alertas = Alerta.objects.filter(
        origen=origen, fecha_apertura__gte=periodo.inicio, fecha_apertura__lt=periodo.fin,
    )
    if ubicaciones is not None:
        if origen == 'IoT':
            alertas = alertas.filter(sensor__ubicacion_id__in=ubicaciones)
        else:
            activos = Activo.objects.filter(ubicacion_id__in=ubicaciones).values_list('id', flat=True)
            alertas = alertas.filter(host_problema_zabbix__activo_id__in=list(activos))
    return alertas


def _por_severidad(alertas) -> dict:
    return {f['severidad']: f['n'] for f in alertas.values('severidad').annotate(n=Count('id'))}


def _abiertas_al_cierre(alertas, periodo: Periodo) -> int:
    return alertas.filter(Q(estado__in=ESTADOS_ABIERTOS) | Q(fecha_cierre__gte=periodo.fin)).count()


def _alertas_ambientales(periodo: Periodo, ubicaciones: set[int] | None) -> dict:
    alertas = _alertas(periodo, 'IoT', ubicaciones)
    cerradas = [
        (a.fecha_cierre - a.fecha_apertura).total_seconds() / 60
        for a in alertas.filter(fecha_cierre__isnull=False).only('fecha_apertura', 'fecha_cierre')
    ]
    return {
        'total': alertas.count(),
        'por_severidad': _por_severidad(alertas),
        'abiertas_al_cierre': _abiertas_al_cierre(alertas, periodo),
        'resolucion_promedio_min': _redondear(sum(cerradas) / len(cerradas)) if cerradas else None,
        # Solo las cerradas desde que existe alerta.fecha_cierre tienen tiempo de resolución.
        'resolucion_con_datos': len(cerradas),
    }


def _problemas_zabbix(periodo: Periodo, ubicaciones: set[int] | None) -> dict:
    alertas = _alertas(periodo, 'Zabbix', ubicaciones)
    por_severidad = _por_severidad(alertas)
    return {
        'total': alertas.count(),
        'por_severidad': por_severidad,
        'altos_o_criticos': sum(por_severidad.get(s, 0) for s in SEVERIDADES_ALTAS),
        'abiertos_al_cierre': _abiertas_al_cierre(alertas, periodo),
    }


def _intervenciones(periodo: Periodo) -> dict:
    """Las solicitadas en el período, por su estado actual (CP-BI-04: cantidad por estado).

    No se filtran por zona: el rack llega como texto libre desde Microsoft Forms.
    """
    del_periodo = Intervencion.objects.annotate(referencia=Coalesce('fecha_solicitud', 'fecha_inicio')).filter(
        referencia__gte=periodo.inicio, referencia__lt=periodo.fin,
    )
    por_estado = {f['estado']: f['n'] for f in del_periodo.values('estado').annotate(n=Count('id'))}
    cerradas = sum(n for e, n in por_estado.items() if e in ESTADOS_CERRADOS)
    return {
        'total': sum(por_estado.values()),
        'por_estado': por_estado,
        'cerradas': cerradas,
        'abiertas': sum(por_estado.values()) - cerradas,
    }


def _accesos(periodo: Periodo, ubicaciones: set[int] | None) -> dict:
    eventos = EventoAcceso.objects.filter(fecha_hora__gte=periodo.inicio, fecha_hora__lt=periodo.fin)
    if ubicaciones is not None:
        eventos = eventos.filter(punto_acceso__ubicacion_id__in=ubicaciones)
    por_resultado = {f['resultado']: f['n'] for f in eventos.values('resultado').annotate(n=Count('id'))}
    return {
        'permitidos': por_resultado.get('Permitido', 0),
        'denegados': por_resultado.get('Denegado', 0),
        # "Error" es una falla de captura del lector, no un intento de acceso rechazado.
        'fallas_del_lector': por_resultado.get('Error', 0),
    }


NIVEL_SEVERIDAD = {'Critica': 'critico', 'Alta': 'critico', 'Advertencia': 'advertencia', 'Informativa': 'neutro'}
ETIQUETA_SEVERIDAD = {'Critica': 'Crítica', 'Alta': 'Alta', 'Advertencia': 'Advertencia', 'Informativa': 'Informativa'}
ETIQUETA_ESTADO = {'Ejecutada': 'Ejecutada', 'Fallida': 'Fallida', 'Cancelada': 'Cancelada', 'Rechazada': 'Rechazada'}


def _eventos_destacados(periodo: Periodo, ubicaciones: set[int] | None) -> list[dict]:
    eventos = []
    zabbix = _alertas(periodo, 'Zabbix', ubicaciones).filter(severidad__in=SEVERIDADES_ALTAS).order_by('-fecha_apertura')[:20]
    for a in zabbix:
        host, separador, problema = a.condicion.partition(': ')
        eventos.append({
            'tipo': 'zabbix', 'nivel': NIVEL_SEVERIDAD.get(a.severidad, 'neutro'),
            'etiqueta': ETIQUETA_SEVERIDAD.get(a.severidad, a.severidad),
            'titulo': problema if separador else a.condicion, 'fuente': host if separador else 'Zabbix',
            'fecha': a.fecha_apertura,
        })
    ambiente = _alertas(periodo, 'IoT', ubicaciones).select_related('sensor').order_by('-fecha_apertura')[:20]
    for a in ambiente:
        eventos.append({
            'tipo': 'ambiente', 'nivel': NIVEL_SEVERIDAD.get(a.severidad, 'neutro'),
            'etiqueta': ETIQUETA_SEVERIDAD.get(a.severidad, a.severidad),
            'titulo': a.condicion.split(':', 1)[0], 'fuente': a.sensor.codigo if a.sensor_id else 'Ambiente',
            'fecha': a.fecha_apertura,
        })
    cerradas = Intervencion.objects.filter(
        estado__in=ESTADOS_CERRADOS, fecha_cierre__gte=periodo.inicio, fecha_cierre__lt=periodo.fin,
    ).order_by('-fecha_cierre')[:20]
    for i in cerradas:
        eventos.append({
            'tipo': 'intervencion', 'nivel': 'ok' if i.estado == 'Ejecutada' else 'advertencia',
            'etiqueta': ETIQUETA_ESTADO.get(i.estado, i.estado),
            'titulo': f'Intervención #{i.id} {(i.rack or i.objetivo or "").strip()}'.strip(),
            'fuente': 'Intervenciones', 'fecha': i.fecha_cierre,
        })
    # Lo más grave primero (Crítica antes que Alta) y, dentro de cada nivel, lo más reciente.
    prioridad = {'critico': 0, 'advertencia': 1, 'ok': 2, 'neutro': 3}
    eventos.sort(key=lambda e: e['fecha'], reverse=True)
    eventos.sort(key=lambda e: (prioridad.get(e['nivel'], 3), e['etiqueta'] != 'Crítica'))
    return eventos[:EVENTOS_DESTACADOS]


def construir_reporte(periodo: Periodo) -> dict:
    ubicaciones = ubicaciones_de(periodo.zona) if periodo.zona else None
    return {
        'periodo': {
            'desde': periodo.desde,
            'hasta': periodo.hasta,
            'dias': periodo.dias,
            'zona': {'id': periodo.zona.id, 'nombre': nombre_ubicacion(periodo.zona)} if periodo.zona else None,
        },
        'disponibilidad': disponibilidad(periodo, ubicaciones),
        'ambiente': _ambiente(periodo, ubicaciones),
        'alertas_ambientales': _alertas_ambientales(periodo, ubicaciones),
        'problemas_zabbix': _problemas_zabbix(periodo, ubicaciones),
        'intervenciones': _intervenciones(periodo),
        'accesos': _accesos(periodo, ubicaciones),
        'eventos': _eventos_destacados(periodo, ubicaciones),
    }
