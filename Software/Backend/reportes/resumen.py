"""Resumen en palabras del reporte: redactado por Gemini o, si no se puede, por una plantilla.

Reglas:
  - A Gemini solo van cifras agregadas del período: nada de nombres de personas, hosts, IPs, zonas
    ni textos de alertas (en el nivel gratuito Google puede usar lo que recibe).
  - Toda cifra del texto de Gemini debe estar en los datos enviados; si inventa una, se descarta.
  - Si falta la clave, Gemini falla o no pasa la verificación, se usa la plantilla: el reporte
    siempre tiene resumen.
  - Se guarda en caché según los datos: recargar la pantalla no vuelve a llamar a Gemini.
"""
from decimal import ROUND_HALF_UP, Decimal
import hashlib
import json
import logging
import re

from django.core.cache import cache

from integraciones import actividad

from . import gemini


logger = logging.getLogger(__name__)

CACHE_TEXTO = 6 * 3600
CACHE_FALLA = 120  # tras una falla (p. ej. cupo agotado) no se reintenta en cada carga
CLAVE_ACTIVIDAD = 'gemini'
LARGO_MAXIMO = 1500

INSTRUCCIONES = (
    'Eres el redactor de informes de SICMA, un sistema que monitorea un datacenter. Recibes en JSON las '
    'cifras de un período. Redacta un resumen de 4 a 6 líneas en español de Chile, tono formal, en un solo '
    'párrafo, sin títulos, viñetas ni formato markdown. Usa solamente las cifras que aparecen en el JSON, '
    'escritas igual (decimales con coma y sin separador de miles), sin calcular porcentajes, diferencias ni '
    'totales nuevos. Si un valor es null, di que no hay datos de ese indicador. No inventes causas, nombres '
    'ni recomendaciones.'
)


# ------------------------------------------------------------------ formato

def _redondeo(valor, decimales: int) -> str:
    """Redondeo habitual (99.25 -> 99.3), no el "del banquero" de Python (99.25 -> 99.2)."""
    return str(Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP))


def numero(valor, decimales: int = 1) -> str:
    """99.25 -> '99,3'; 12.0 -> '12'; 1086 -> '1086' (sin separador de miles, igual que en los datos)."""
    if isinstance(valor, int):
        return str(valor)
    texto = _redondeo(valor, decimales)
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto.replace('.', ',')


def fecha(iso) -> str:
    return iso.strftime('%d-%m-%Y') if hasattr(iso, 'strftime') else str(iso)


def plural(n: int, singular: str, plural_: str | None = None) -> str:
    return f'{n} {singular if n == 1 else (plural_ or singular + "s")}'


# ------------------------------------------------------------------ datos que se envían

def datos_para_ia(reporte: dict) -> dict:
    """Solo cifras agregadas y el rango de fechas."""
    p, a, z, i, ac, amb = (reporte[k] for k in ('periodo', 'alertas_ambientales', 'problemas_zabbix',
                                                  'intervenciones', 'accesos', 'ambiente'))
    criticas = a['por_severidad'].get('Critica', 0) + a['por_severidad'].get('Alta', 0)
    return {
        'periodo': {'desde': str(p['desde']), 'hasta': str(p['hasta']), 'dias': p['dias'],
                    'filtrado_por_zona': p['zona'] is not None},
        'disponibilidad_servidores_pct': reporte['disponibilidad']['porcentaje'],
        'ambiente': {
            'lecturas': amb['lecturas'],
            'temperatura_promedio_c': amb['temperatura']['promedio'],
            'temperatura_maxima_c': amb['temperatura']['maximo'],
            'humedad_promedio_pct': amb['humedad']['promedio'],
        },
        'alertas_ambientales': {
            'total': a['total'], 'altas_o_criticas': criticas,
            'resolucion_promedio_min': a['resolucion_promedio_min'],
        },
        'problemas_zabbix': {
            'total': z['total'], 'altos_o_criticos': z['altos_o_criticos'],
            'abiertos_al_cierre': z['abiertos_al_cierre'],
        },
        'intervenciones': {'solicitadas': i['total'], 'cerradas': i['cerradas'], 'abiertas': i['abiertas']},
        'accesos': {'permitidos': ac['permitidos'], 'denegados': ac['denegados'],
                    'fallas_del_lector': ac['fallas_del_lector']},
    }


# ------------------------------------------------------------------ plantilla

def resumen_plantilla(reporte: dict) -> str:
    p, d, amb, a, z, i, ac = (reporte[k] for k in ('periodo', 'disponibilidad', 'ambiente', 'alertas_ambientales',
                                                     'problemas_zabbix', 'intervenciones', 'accesos'))
    lugar = f' en {p["zona"]["nombre"]}' if p['zona'] else ''
    partes = [f'Entre el {fecha(p["desde"])} y el {fecha(p["hasta"])}{lugar}']
    if d['porcentaje'] is not None:
        partes[0] += f', los servidores monitoreados por Zabbix tuvieron una disponibilidad promedio de {numero(d["porcentaje"])} %.'
    else:
        partes[0] += ', no hay datos de disponibilidad de los servidores.'

    if amb['lecturas']:
        partes.append(
            f'La temperatura promedio fue {numero(amb["temperatura"]["promedio"])} °C '
            f'(máxima {numero(amb["temperatura"]["maximo"])} °C) y la humedad promedio '
            f'{numero(amb["humedad"]["promedio"])} %.'
        )
    else:
        partes.append('No hubo lecturas ambientales reales en el período.')

    texto = f'Se registraron {plural(a["total"], "alerta ambiental", "alertas ambientales")}'
    if a['resolucion_promedio_min'] is not None:
        texto += f', resueltas en {numero(a["resolucion_promedio_min"])} min en promedio'
    texto += (f', y Zabbix reportó {plural(z["total"], "problema")}, '
              f'{z["altos_o_criticos"]} de severidad alta o crítica.')
    partes.append(texto)

    partes.append(
        f'Se solicitaron {plural(i["total"], "intervención", "intervenciones")}: '
        f'{i["cerradas"]} {"cerrada" if i["cerradas"] == 1 else "cerradas"} y '
        f'{i["abiertas"]} {"abierta" if i["abiertas"] == 1 else "abiertas"}.'
    )
    texto = (f'El control de acceso registró {plural(ac["permitidos"], "ingreso permitido", "ingresos permitidos")} '
             f'y {plural(ac["denegados"], "intento denegado", "intentos denegados")}')
    if ac['fallas_del_lector']:
        texto += f', además de {plural(ac["fallas_del_lector"], "falla", "fallas")} de captura del lector'
    partes.append(texto + '.')
    return ' '.join(partes)


# ------------------------------------------------------------------ verificación de cifras

NUMERO = re.compile(r'\d+(?:[.,]\d+)*')


def _normalizar(texto: str) -> str:
    texto = texto.replace(',', '.')
    if texto.count('.') > 1:
        return texto  # p. ej. "1.086.000": no se reinterpreta
    entero, _, decimal = texto.partition('.')
    entero = entero.lstrip('0') or '0'
    decimal = decimal.rstrip('0')
    return f'{entero}.{decimal}' if decimal else entero


def _permitidos(datos) -> set[str]:
    permitidos = set()

    def recorrer(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, int):
            permitidos.add(_normalizar(str(v)))
            if v >= 1000:
                permitidos.add(_normalizar(f'{v:,}'.replace(',', '.')))
        elif isinstance(v, float):
            for formato in (f'{v}', f'{v:.2f}', f'{v:.1f}', f'{round(v)}',
                            _redondeo(v, 2), _redondeo(v, 1), _redondeo(v, 0)):
                permitidos.add(_normalizar(formato))
        elif isinstance(v, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            for parte in v.split('-'):
                permitidos.add(_normalizar(parte))
        elif isinstance(v, dict):
            for x in v.values():
                recorrer(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                recorrer(x)

    recorrer(datos)
    return permitidos


def cifras_ajenas(texto: str, datos: dict) -> list[str]:
    """Las cifras del texto que no están en los datos (vacío = el texto no inventa números)."""
    permitidos = _permitidos(datos)
    return [n for n in NUMERO.findall(texto) if _normalizar(n) not in permitidos]


def _limpiar(texto: str) -> str:
    texto = re.sub(r'[*#_`>]+', '', texto)
    texto = re.sub(r'^\s*[-•]\s*', '', texto, flags=re.M)
    return re.sub(r'\s+', ' ', texto).strip()[:LARGO_MAXIMO]


# ------------------------------------------------------------------ resumen

def resumen(reporte: dict) -> dict:
    plantilla = {'texto': resumen_plantilla(reporte), 'origen': 'plantilla', 'modelo': None, 'motivo': None}
    if not gemini.configurado():
        return {**plantilla, 'motivo': 'Resumen con IA desactivado: falta GEMINI_API_KEY.'}

    datos = datos_para_ia(reporte)
    clave = 'reportes:ia:' + hashlib.sha256(json.dumps(datos, sort_keys=True).encode()).hexdigest()
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado if guardado.get('origen') == 'ia' else {**plantilla, 'motivo': guardado.get('motivo')}

    try:
        texto = _limpiar(gemini.generar(json.dumps(datos, ensure_ascii=False), INSTRUCCIONES))
        ajenas = cifras_ajenas(texto, datos)
        if ajenas:
            raise gemini.GeminiNoDisponible(
                'El texto de la IA traía cifras que no están en los datos; se usó la plantilla.'
            )
    except gemini.GeminiNoDisponible as error:
        motivo = str(error)
        logger.warning('Resumen con IA no disponible: %s', motivo)
        actividad.latido(CLAVE_ACTIVIDAD, error=motivo)
        cache.set(clave, {'origen': 'plantilla', 'motivo': motivo}, CACHE_FALLA)
        return {**plantilla, 'motivo': motivo}

    actividad.latido(CLAVE_ACTIVIDAD)
    resultado = {'texto': texto, 'origen': 'ia', 'modelo': gemini.modelo(), 'motivo': None}
    cache.set(clave, resultado, CACHE_TEXTO)
    return resultado
