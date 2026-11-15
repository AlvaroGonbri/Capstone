"""Correo a los Administradores Privilegiados cada vez que se renueva un secreto."""
import logging
import threading
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import close_old_connections

from .secretos import SECRETOS, nombre_de


logger = logging.getLogger(__name__)


def _enviar(asunto: str, cuerpo: str, destinatarios: list[str]) -> None:
    try:
        # En copia oculta: cada privilegiado recibe el aviso sin ver las cuentas de los demás.
        EmailMessage(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, bcc=destinatarios).send()
    except Exception:
        logger.exception('No fue posible enviar el aviso de renovación de secreto.')
    finally:
        close_old_connections()


def avisar_renovacion(nombre: str, usuario, ip: str, fila, inmediato: bool) -> None:
    destinatarios = list(
        get_user_model().objects.filter(is_active=True, groups__name='AdministradorPrivilegiado')
        .exclude(email='').values_list('email', flat=True).distinct()
    )
    if not destinatarios:
        return
    zona = ZoneInfo(settings.SICMA_ZONA_HORARIA)
    secreto = SECRETOS[nombre].nombre
    cuando = fila.renovado_en.astimezone(zona)
    if inmediato or not fila.anterior_valido_hasta:
        anterior = 'El valor anterior dejó de servir de inmediato.'
    else:
        anterior = f'El valor anterior sigue sirviendo hasta el {fila.anterior_valido_hasta.astimezone(zona):%d-%m-%Y a las %H:%M}.'
    asunto = f'[SICMA] Se renovó el {secreto}'
    cuerpo = (
        f'{nombre_de(usuario)} renovó el {secreto} el {cuando:%d-%m-%Y a las %H:%M} '
        f'desde la IP {ip or "desconocida"}.\n\n'
        f'{anterior}\n\n'
        'Si no reconoces este cambio, revisa el registro en la vista Integraciones de SICMA, vuelve a '
        'renovar el secreto anulando el anterior de inmediato y cambia tu contraseña.\n\n'
        'Este correo no incluye el valor del secreto.'
    )
    if getattr(settings, 'ALERTAS_CORREO_ASINCRONO', True):
        threading.Thread(target=_enviar, args=(asunto, cuerpo, destinatarios), daemon=True).start()
    else:
        _enviar(asunto, cuerpo, destinatarios)
