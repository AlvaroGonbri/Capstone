"""Lectura del buzón de SICMA: así llegan los avisos del flujo de Power Automate (RF-INT-01 a 03).

Con la licencia gratuita de Power Automate no hay conectores HTTP, así que el flujo escribe a
SICMA por correo (Outlook, conector estándar) y SICMA lee su buzón por IMAP cada minuto.

Cada correo del flujo lleva en el asunto la etiqueta [SICMA-INT] y en el cuerpo un JSON:
    {"tipo": "nueva", "token": "...", "forms_id": "...", "correo": "...", "nombre": "...",
     "rack": "...", "fecha": "2026-10-20", "hora": "14:30", "servicios": "..."}
    {"tipo": "decision", "token": "...", "forms_id": "...", "decision": "Approve",
     "decisor": "jefatura@...", "comentario": "..."}
Solo se aceptan si vienen de INTERVENCIONES_CORREO_FLUJO y traen INTERVENCIONES_TOKEN.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import message_from_bytes, policy
from email.utils import parseaddr
import hmac
import html
import imaplib
import json
import logging
import re
from zoneinfo import ZoneInfo

from django.conf import settings
from rest_framework import serializers

from . import servicio
from .servicio import ETIQUETA_ASUNTO, TransicionInvalida


logger = logging.getLogger(__name__)

DECISIONES_APROBAR = {'approve', 'approved', 'aprobar', 'aprobada', 'aprobado', 'aprobación'}
DECISIONES_RECHAZAR = {'reject', 'rejected', 'rechazar', 'rechazada', 'rechazado', 'rechazo'}


class MensajeInvalido(Exception):
    """El correo no es del flujo o su contenido no es válido. Se marca como leído y se descarta."""


FORMATOS_HORA = ['%H:%M', '%H:%M:%S', '%H.%M', '%H']


class SolicitudFormsSerializer(serializers.Serializer):
    forms_id = serializers.CharField(max_length=100)
    correo = serializers.EmailField(max_length=254)
    nombre = serializers.CharField(max_length=200)
    rack = serializers.CharField(max_length=200)
    fecha = serializers.DateField(input_formats=['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', 'iso-8601'])
    hora = serializers.TimeField(input_formats=FORMATOS_HORA)
    # Opcional: si el formulario pide la hora de término, la intervención llega con su horario completo.
    hora_termino = serializers.TimeField(input_formats=FORMATOS_HORA, required=False, allow_null=True)
    descripcion = serializers.CharField(allow_blank=True, allow_null=True, required=False, default='')
    plan_reversa = serializers.CharField(allow_blank=True, allow_null=True, required=False, default='')
    servicios = serializers.CharField(allow_blank=True, allow_null=True, required=False, default='')


class DecisionSerializer(serializers.Serializer):
    forms_id = serializers.CharField(max_length=100)
    decision = serializers.CharField(max_length=50)
    # Power Automate envía null si el aprobador no dejó comentario.
    decisor = serializers.CharField(max_length=254, allow_blank=True, allow_null=True, required=False, default='')
    comentario = serializers.CharField(allow_blank=True, allow_null=True, required=False, default='')

    def validate_decision(self, valor):
        valor = valor.strip().lower()
        if valor not in DECISIONES_APROBAR | DECISIONES_RECHAZAR:
            raise serializers.ValidationError('Decisión desconocida.')
        return valor in DECISIONES_APROBAR


@dataclass
class Resultado:
    tipo: str
    intervencion_id: int
    nueva: bool  # False si el correo repetía algo ya registrado


def extraer_json(cuerpo):
    """El cuerpo puede venir en HTML (Outlook): se quitan etiquetas y entidades antes de leer el JSON."""
    # Fuera <style>/<head> (Outlook trae CSS con llaves) y luego todas las etiquetas. En texto plano,
    # Outlook escribe los enlaces como 'texto <destino>': se quita el destino y el espacio previo.
    texto = re.sub(r'<(style|script|head)\b.*?</\1\s*>', '', cuerpo or '', flags=re.S | re.I)
    texto = html.unescape(re.sub(r'\s*<[^<>]*>', '', texto))
    # Outlook corta las líneas largas (incluso dentro de un valor), usa espacios duros y puede
    # cambiar las comillas por tipográficas. Un JSON válido no necesita saltos de línea reales:
    # los que vengan dentro de un texto llegan escapados como \n y se conservan.
    texto = re.sub(r'[\r\n​﻿]', '', texto).replace('\t', ' ').replace('\xa0', ' ')
    texto = texto.translate(str.maketrans('“”', '""'))
    inicio, fin = texto.find('{'), texto.rfind('}')
    if inicio < 0 or fin <= inicio:
        raise MensajeInvalido('El cuerpo no contiene un JSON.')
    try:
        datos = json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError as error:
        raise MensajeInvalido(f'JSON inválido: {error}') from error
    if not isinstance(datos, dict):
        raise MensajeInvalido('El JSON debe ser un objeto.')
    return datos


def _validar(serializer_class, datos):
    serializer = serializer_class(data=datos)
    if not serializer.is_valid():
        raise MensajeInvalido(f'Datos inválidos: {serializer.errors}')
    return serializer.validated_data


def procesar_mensaje(remitente, asunto, cuerpo):
    """Valida y aplica un correo del flujo. Lanza MensajeInvalido si debe descartarse."""
    correo_flujo = getattr(settings, 'INTERVENCIONES_CORREO_FLUJO', '')
    token = getattr(settings, 'INTERVENCIONES_TOKEN', '')
    if not correo_flujo or not token:
        raise MensajeInvalido('Faltan INTERVENCIONES_CORREO_FLUJO o INTERVENCIONES_TOKEN en la configuración.')
    if ETIQUETA_ASUNTO not in (asunto or ''):
        raise MensajeInvalido('El asunto no trae la etiqueta [SICMA-INT].')
    if parseaddr(remitente or '')[1].lower() != correo_flujo.lower():
        raise MensajeInvalido(f'Remitente no autorizado: {remitente}')

    datos = extraer_json(cuerpo)
    if not hmac.compare_digest(str(datos.get('token', '')), token):
        raise MensajeInvalido('Token no válido.')

    tipo = str(datos.get('tipo', '')).strip().lower()
    try:
        if tipo == 'nueva':
            v = _validar(SolicitudFormsSerializer, datos)
            zona = ZoneInfo(settings.SICMA_ZONA_HORARIA)
            inicio = datetime.combine(v['fecha'], v['hora'], tzinfo=zona)
            termino = None
            if v.get('hora_termino'):
                termino = datetime.combine(v['fecha'], v['hora_termino'], tzinfo=zona)
                if termino <= inicio:
                    termino += timedelta(days=1)  # p. ej. 23:00 a 02:00: termina al día siguiente
            intervencion, creada = servicio.crear_desde_forms(
                v['forms_id'].strip(), v['nombre'].strip(), v['correo'].strip(), v['rack'].strip(),
                (v['servicios'] or '').strip(), inicio, termino,
                (v['descripcion'] or '').strip(), (v['plan_reversa'] or '').strip(),
            )
            return Resultado('nueva', intervencion.id, creada)
        if tipo == 'decision':
            v = _validar(DecisionSerializer, datos)
            intervencion, registrada = servicio.registrar_decision(
                v['forms_id'].strip(), v['decision'], (v['decisor'] or '').strip(), (v['comentario'] or '').strip(),
            )
            return Resultado('decision', intervencion.id, registrada)
    except TransicionInvalida as error:
        raise MensajeInvalido(str(error)) from error
    raise MensajeInvalido(f'Tipo de mensaje desconocido: {tipo!r}')


def _texto_del_correo(mensaje):
    parte = mensaje.get_body(preferencelist=('plain', 'html'))
    return parte.get_content() if parte else ''


def leer_buzon():
    """Procesa los correos no leídos con la etiqueta. Devuelve (procesados, descartados).

    Se leen con BODY.PEEK y se marcan como leídos recién después de procesarlos: si la base de
    datos falla, el correo queda sin leer y se reintenta en la pasada siguiente.
    """
    host = getattr(settings, 'INTERVENCIONES_IMAP_HOST', 'imap.gmail.com')
    usuario, clave = settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD
    if not usuario or not clave:
        raise RuntimeError('Faltan EMAIL_HOST_USER o EMAIL_HOST_PASSWORD para leer el buzón.')

    procesados, descartados = [], []
    with imaplib.IMAP4_SSL(host, timeout=30) as imap:
        imap.login(usuario, clave)
        imap.select('INBOX')
        _, datos = imap.search(None, 'UNSEEN', 'SUBJECT', '"SICMA-INT"')
        for numero in datos[0].split():
            _, partes = imap.fetch(numero, '(BODY.PEEK[])')
            mensaje = message_from_bytes(partes[0][1], policy=policy.default)
            asunto = str(mensaje.get('Subject', ''))
            if ETIQUETA_ASUNTO + ' AGENDAR' in asunto:
                continue  # copia de un correo que SICMA envió al flujo; no es para SICMA
            try:
                procesados.append(procesar_mensaje(str(mensaje.get('From', '')), asunto, _texto_del_correo(mensaje)))
            except MensajeInvalido as error:
                logger.warning('Correo descartado (%s): %s', asunto, error)
                descartados.append(f'{asunto}: {error}')
            imap.store(numero, '+FLAGS', '\\Seen')
    return procesados, descartados
