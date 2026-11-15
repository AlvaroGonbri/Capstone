"""PDF del reporte (GET /api/reportes/pdf/), con ReportLab (Python puro, sin librerías de sistema).

Usa los mismos datos y el mismo resumen que la pantalla Reportes.
"""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .agregacion import zona_horaria
from .resumen import fecha, numero


PRIMARIO = colors.HexColor('#0e7c86')
TINTA = colors.HexColor('#0f1b24')
TENUE = colors.HexColor('#6b7884')
LINEA = colors.HexColor('#e2e7ec')
FONDO_RESUMEN = colors.HexColor('#f4f1fb')
BORDE_RESUMEN = colors.HexColor('#6d4fc4')

ESTILOS = getSampleStyleSheet()
TITULO = ParagraphStyle('titulo', parent=ESTILOS['Title'], alignment=TA_LEFT, fontSize=18, leading=22,
                        textColor=TINTA, spaceAfter=2)
SUBTITULO = ParagraphStyle('subtitulo', parent=ESTILOS['Normal'], fontSize=9, leading=12, textColor=TENUE)
SECCION = ParagraphStyle('seccion', parent=ESTILOS['Heading2'], fontSize=11.5, leading=14, textColor=TINTA,
                         spaceBefore=10, spaceAfter=5)
NORMAL = ParagraphStyle('normal', parent=ESTILOS['Normal'], fontSize=9.5, leading=13.5, textColor=TINTA)
NOTA = ParagraphStyle('nota', parent=NORMAL, fontSize=7.8, leading=10, textColor=TENUE)
CELDA = ParagraphStyle('celda', parent=NORMAL, fontSize=8.5, leading=11)

ESTILO_TABLA = TableStyle([
    ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
    ('TEXTCOLOR', (0, 0), (-1, 0), TENUE),
    ('FONT', (0, 1), (-1, -1), 'Helvetica', 8.5),
    ('TEXTCOLOR', (0, 1), (-1, -1), TINTA),
    ('LINEBELOW', (0, 0), (-1, 0), 0.6, LINEA),
    ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINEA),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
])

ESTADOS_INTERVENCION = {
    'Pendiente': 'Por aprobar', 'CambiosSolicitados': 'Cambios solicitados', 'Aprobada': 'Aprobada',
    'EnEjecucion': 'En ejecución', 'Ejecutada': 'Ejecutada', 'Fallida': 'Fallida',
    'Cancelada': 'Cancelada', 'Rechazada': 'Rechazada',
}


def _p(texto, estilo=CELDA) -> Paragraph:
    return Paragraph(escape(str(texto)), estilo)


def _grafico_disponibilidad(por_dia: list[dict], ancho: float, alto: float = 48 * mm) -> Drawing:
    """Línea de disponibilidad diaria. Los días sin datos cortan la línea."""
    d = Drawing(ancho, alto)
    izq, der, arr, aba = 30, 8, 8, 16
    valores = [p['porcentaje'] for p in por_dia if p['porcentaje'] is not None]
    if not valores:
        d.add(String(ancho / 2, alto / 2, 'Sin datos de disponibilidad en el período', fontName='Helvetica',
                     fontSize=9, fillColor=TENUE, textAnchor='middle'))
        return d
    minimo = min(90.0, (int(min(valores)) // 5) * 5)
    n = len(por_dia)

    def x(i):
        return izq + (ancho - izq - der) * (0.5 if n == 1 else i / (n - 1))

    def y(v):
        return aba + (alto - aba - arr) * (v - minimo) / (100 - minimo)

    paso = 5 if 100 - minimo <= 20 else 10
    for marca in range(int(minimo), 101, paso):
        d.add(Line(izq, y(marca), ancho - der, y(marca), strokeColor=LINEA, strokeWidth=0.5))
        d.add(String(izq - 4, y(marca) - 3, f'{marca} %', fontName='Helvetica', fontSize=7, fillColor=TENUE,
                     textAnchor='end'))
    tramo: list[float] = []
    ultimo = None
    for i, punto in enumerate(por_dia):
        if punto['porcentaje'] is None:
            if len(tramo) >= 4:
                d.add(PolyLine(tramo, strokeColor=PRIMARIO, strokeWidth=1.6))
            tramo = []
            continue
        tramo += [x(i), y(punto['porcentaje'])]
        ultimo = (i, punto['porcentaje'])
    if len(tramo) >= 4:
        d.add(PolyLine(tramo, strokeColor=PRIMARIO, strokeWidth=1.6))
    elif len(tramo) == 2:
        d.add(Circle(tramo[0], tramo[1], 1.8, fillColor=PRIMARIO, strokeColor=None))
    if ultimo:
        d.add(Circle(x(ultimo[0]), y(ultimo[1]), 2.4, fillColor=PRIMARIO, strokeColor=colors.white, strokeWidth=1))
    marcas = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1}) if n > 8 else range(n)
    for i in marcas:
        dia = datetime.fromisoformat(por_dia[i]['fecha'])
        d.add(String(x(i), 3, f'{dia:%d-%m}', fontName='Helvetica', fontSize=7, fillColor=TENUE, textAnchor='middle'))
    return d


def generar_pdf(reporte: dict, resumen: dict, usuario: str) -> bytes:
    salida = BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title='SICMA · Reporte del período', author='SICMA',
    )
    ancho = A4[0] - 36 * mm
    p, d, amb, a, z, i, ac = (reporte[k] for k in ('periodo', 'disponibilidad', 'ambiente', 'alertas_ambientales',
                                                     'problemas_zabbix', 'intervenciones', 'accesos'))
    ahora = timezone.now().astimezone(zona_horaria())
    zona = p['zona']['nombre'] if p['zona'] else 'Todas las zonas'

    historia = [
        Paragraph('SICMA · Reporte del período', TITULO),
        Paragraph(escape(f'Del {fecha(p["desde"])} al {fecha(p["hasta"])} ({p["dias"]} días) · {zona} · '
                         f'generado el {ahora:%d-%m-%Y %H:%M} por {usuario}'), SUBTITULO),
        Spacer(1, 8),
    ]

    # Resumen, con el aviso de cómo se redactó.
    origen = (f'con inteligencia artificial ({resumen["modelo"]}), solo a partir de las cifras de este reporte'
              if resumen['origen'] == 'ia' else 'con una plantilla de SICMA, sin inteligencia artificial')
    caja = Table(
        [[Paragraph(escape(resumen['texto']), NORMAL)],
         [Paragraph(escape(f'Este párrafo fue redactado automáticamente a partir de los datos del período, {origen}.'), NOTA)]],
        colWidths=[ancho],
    )
    caja.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), FONDO_RESUMEN),
        ('LINEBEFORE', (0, 0), (0, -1), 2.5, BORDE_RESUMEN),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, 0), 8), ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    historia += [caja, Spacer(1, 10)]

    # Indicadores
    disponibilidad = f'{numero(d["porcentaje"])} %' if d['porcentaje'] is not None else 'Sin datos'
    resolucion = (f'{numero(a["resolucion_promedio_min"])} min en promedio' if a['resolucion_promedio_min'] is not None
                  else 'sin tiempo de resolución')
    kpis = Table(
        [['Disponibilidad', 'Alertas ambientales', 'Problemas Zabbix', 'Intervenciones', 'Accesos permitidos'],
         [disponibilidad, str(a['total']), str(z['total']), f'{i["cerradas"]} / {i["total"]}', str(ac['permitidos'])],
         [_p('servidores (agente Zabbix)', NOTA), _p(resolucion, NOTA),
          _p(f'{z["altos_o_criticos"]} altos o críticos', NOTA), _p(f'cerradas / solicitadas · {i["abiertas"]} abiertas', NOTA),
          _p(f'{ac["denegados"]} denegados · {ac["fallas_del_lector"]} fallas del lector', NOTA)]],
        colWidths=[ancho / 5] * 5,
    )
    kpis.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica', 7.8), ('TEXTCOLOR', (0, 0), (-1, 0), TENUE),
        ('FONT', (0, 1), (-1, 1), 'Helvetica-Bold', 15), ('TEXTCOLOR', (0, 1), (-1, 1), TINTA),
        ('BOX', (0, 0), (-1, -1), 0.5, LINEA), ('INNERGRID', (0, 0), (-1, -1), 0.5, LINEA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 1), (-1, 1), 2),
    ]))
    historia.append(kpis)

    # Disponibilidad
    seccion = [Paragraph('Disponibilidad de servidores por día', SECCION),
               _grafico_disponibilidad(d['por_dia'], ancho)]
    if d['error']:
        seccion.append(Paragraph(escape(d['error']), NOTA))
    seccion.append(Paragraph('Promedio diario de los servidores, según el ítem de disponibilidad del agente de Zabbix '
                             '(tendencias por hora). Las horas sin datos de Zabbix no se cuentan.', NOTA))
    historia.append(KeepTogether(seccion))
    if d['hosts']:
        filas = [['Servidor', 'Disponibilidad', 'Horas sin disponibilidad', 'Horas con datos']]
        filas += [[h['host'], f'{numero(h["porcentaje"], 2)} %' if h['porcentaje'] is not None else 'Sin datos',
                   numero(h['horas_sin_disponibilidad']), str(h['horas_con_datos'])] for h in d['hosts']]
        tabla = Table(filas, colWidths=[ancho * 0.34, ancho * 0.22, ancho * 0.24, ancho * 0.2])
        tabla.setStyle(ESTILO_TABLA)
        historia += [Spacer(1, 6), tabla]

    # Ambiente, intervenciones y accesos
    t, h = amb['temperatura'], amb['humedad']
    ambiente = [['Variable', 'Promedio', 'Mínimo', 'Máximo']]
    if amb['lecturas']:
        ambiente += [['Temperatura (°C)', numero(t['promedio']), numero(t['minimo']), numero(t['maximo'])],
                     ['Humedad (%)', numero(h['promedio']), numero(h['minimo']), numero(h['maximo'])]]
    else:
        ambiente += [['Sin lecturas reales en el período', '', '', '']]
    tabla_amb = Table(ambiente, colWidths=[ancho * 0.4, ancho * 0.2, ancho * 0.2, ancho * 0.2])
    tabla_amb.setStyle(ESTILO_TABLA)
    historia.append(KeepTogether([
        Paragraph('Ambiente', SECCION), tabla_amb,
        Paragraph(escape(f'{amb["lecturas"]} lecturas reales; las simuladas no se incluyen (RN-06).'), NOTA),
    ]))

    filas = [['Estado actual', 'Intervenciones']]
    filas += [[ESTADOS_INTERVENCION.get(e, e), str(n)] for e, n in sorted(i['por_estado'].items(), key=lambda x: -x[1])]
    if len(filas) == 1:
        filas.append(['Sin intervenciones solicitadas en el período', ''])
    tabla_int = Table(filas, colWidths=[ancho * 0.6, ancho * 0.4])
    tabla_int.setStyle(ESTILO_TABLA)
    historia.append(KeepTogether([
        Paragraph('Intervenciones solicitadas en el período', SECCION), tabla_int,
        Paragraph('No se filtran por zona: el rack llega como texto desde Microsoft Forms.', NOTA) if p['zona'] else Spacer(1, 0),
    ]))

    # Eventos destacados
    if reporte['eventos']:
        filas = [['Fecha', 'Tipo', 'Evento', 'Origen']]
        for e in reporte['eventos']:
            cuando = e['fecha'].astimezone(zona_horaria()) if hasattr(e['fecha'], 'astimezone') else e['fecha']
            filas.append([f'{cuando:%d-%m %H:%M}' if hasattr(cuando, 'strftime') else str(cuando),
                          e['etiqueta'], _p(e['titulo']), _p(e['fuente'])])
        tabla_ev = Table(filas, colWidths=[ancho * 0.14, ancho * 0.14, ancho * 0.5, ancho * 0.22], repeatRows=1)
        tabla_ev.setStyle(ESTILO_TABLA)
        historia.append(KeepTogether([Paragraph('Eventos destacados', SECCION), tabla_ev]))

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(TENUE)
        canvas.drawString(18 * mm, 9 * mm, 'SICMA · Sistema Integrado de Control y Monitoreo de Activos')
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f'Página {doc.page}')
        canvas.restoreState()

    documento.build(historia, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
