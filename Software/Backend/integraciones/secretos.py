"""Secretos compartidos que SICMA genera y solo verifica: el del webhook de Zabbix y el token del
flujo de Power Automate. Se pueden renovar desde la vista Integraciones (ver CAMBIO_DE_SECRETOS.md).

Los que SICMA usa para conectarse afuera (token de Zabbix, contraseña de Gmail) y los de la
infraestructura (SECRET_KEY, clave de MySQL) siguen solo en el .env o en Windows.
"""
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import RenovacionSecreto, SecretoIntegracion


logger = logging.getLogger(__name__)

WEBHOOK_ZABBIX = 'zabbix_webhook'
FLUJO_INTERVENCIONES = 'intervenciones_flujo'


@dataclass(frozen=True)
class DefinicionSecreto:
    ajuste: str  # variable del .env que vale mientras SICMA no lo haya renovado
    nombre: str


SECRETOS = {
    WEBHOOK_ZABBIX: DefinicionSecreto('ZABBIX_WEBHOOK_SECRET', 'secreto del webhook de Zabbix'),
    FLUJO_INTERVENCIONES: DefinicionSecreto('INTERVENCIONES_TOKEN', 'token del flujo de Power Automate'),
}

# Tras renovar, el secreto anterior sigue sirviendo este tiempo: da margen para pegar el nuevo en
# Zabbix o en el flujo sin perder avisos.
GRACIA = timedelta(hours=24)


def _hash(valor: str) -> str:
    # Los secretos son aleatorios de 256 bits: basta SHA-256 (un hash lento no agrega seguridad
    # y el webhook se verifica en cada aviso).
    return hashlib.sha256(valor.encode()).hexdigest()


def _del_env(nombre: str) -> str:
    return getattr(settings, SECRETOS[nombre].ajuste, '') or ''


def _fila(nombre: str) -> SecretoIntegracion | None:
    try:
        return SecretoIntegracion.objects.filter(nombre=nombre).first()
    except DatabaseError:
        logger.warning('No fue posible leer el secreto %s; se usa el del .env.', nombre, exc_info=True)
        return None


def configurado(nombre: str) -> bool:
    return _fila(nombre) is not None or bool(_del_env(nombre))


def verificar(nombre: str, recibido: object) -> bool:
    """True si `recibido` es el secreto vigente (o el anterior, dentro del período de gracia)."""
    recibido = str(recibido or '')
    if not recibido:
        return False
    fila = _fila(nombre)
    if fila is None:
        esperado = _del_env(nombre)
        return bool(esperado) and hmac.compare_digest(recibido.encode(), esperado.encode())
    calculado = _hash(recibido)
    if hmac.compare_digest(calculado, fila.hash_actual):
        return True
    return bool(
        fila.hash_anterior
        and fila.anterior_valido_hasta
        and timezone.now() < fila.anterior_valido_hasta
        and hmac.compare_digest(calculado, fila.hash_anterior)
    )


def nombre_de(usuario) -> str:
    return (usuario.get_full_name() or usuario.get_username())[:150]


def renovar(nombre: str, usuario, ip: str, inmediato: bool = False) -> tuple[str, SecretoIntegracion]:
    """Genera un secreto nuevo y devuelve su valor, que no se vuelve a poder leer.

    El anterior sigue sirviendo durante GRACIA, salvo `inmediato` (p. ej. si se filtró).
    """
    valor = secrets.token_urlsafe(32)
    ahora = timezone.now()
    with transaction.atomic():
        fila = SecretoIntegracion.objects.select_for_update().filter(nombre=nombre).first()
        if fila is not None:
            anterior = fila.hash_actual
        else:
            del_env = _del_env(nombre)
            anterior = _hash(del_env) if del_env else ''
        if inmediato:
            anterior = ''
        fila, _ = SecretoIntegracion.objects.update_or_create(
            nombre=nombre,
            defaults={
                'hash_actual': _hash(valor),
                'hash_anterior': anterior,
                'anterior_valido_hasta': ahora + GRACIA if anterior else None,
                'renovado_en': ahora,
                'renovado_por': nombre_de(usuario),
            },
        )
        RenovacionSecreto.objects.create(
            secreto=nombre,
            usuario_id=usuario.pk,
            nombre_usuario=nombre_de(usuario),
            fecha=ahora,
            ip=(ip or '')[:45],
            inmediato=inmediato,
        )
    return valor, fila


def estado(nombre: str) -> dict:
    """Lo que la vista puede saber de un secreto: si está configurado y cuándo se renovó."""
    fila = _fila(nombre)
    if fila is None:
        del_env = bool(_del_env(nombre))
        return {
            'configurado': del_env,
            'origen': 'env' if del_env else None,
            'renovado_en': None,
            'renovado_por': None,
            'anterior_valido_hasta': None,
        }
    en_gracia = bool(fila.hash_anterior and fila.anterior_valido_hasta and fila.anterior_valido_hasta > timezone.now())
    return {
        'configurado': True,
        'origen': 'sicma',
        'renovado_en': fila.renovado_en,
        'renovado_por': fila.renovado_por or None,
        'anterior_valido_hasta': fila.anterior_valido_hasta if en_gracia else None,
    }


def renovaciones_recientes(limite: int = 10) -> list[dict]:
    try:
        return [
            {
                'secreto': r.secreto,
                'fecha': r.fecha,
                'usuario': r.nombre_usuario or None,
                'ip': r.ip or None,
                'inmediato': r.inmediato,
            }
            for r in RenovacionSecreto.objects.all()[:limite]
        ]
    except DatabaseError:
        return []
