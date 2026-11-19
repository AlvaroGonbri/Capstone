"""Desbloqueo de la app móvil con huella o PIN del teléfono (RF-PLT-02).

La huella nunca sale del teléfono: Android la verifica y, si coincide, entrega a la app la "llave del
dispositivo" que guardó en su almacén seguro (Keystore). La app canjea la llave aquí por una sesión
nueva de solo lectura, sin pedir la contraseña.

La llave:
  - solo la recibe la app móvil (login con canal=movil) y solo sirve en /api/auth/token/dispositivo/:
    tiene su propio tipo de token, así que no la aceptan ni la API ni la renovación normal;
  - vence 7 días después del último ingreso con contraseña (no se alarga con el uso);
  - es de un solo uso: cada canje la invalida y entrega otra con el mismo vencimiento;
  - deja de servir si cambia la contraseña, si la cuenta se desactiva o bloquea, o al cerrar sesión.

La inactividad (RNF-SEG) sigue vigente: tras unos minutos sin uso la app se bloquea, y desbloquearla
con la huella equivale a volver a iniciar sesión.
"""
import hashlib
from datetime import timedelta

from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import CLAIM_SOLO_LECTURA

DURACION_LLAVE = timedelta(days=7)
CLAIM_CLAVE = 'clave'  # resumen de la contraseña vigente: si cambia, la llave deja de servir


class LlaveDispositivo(RefreshToken):
    token_type = 'llave_dispositivo'
    lifetime = DURACION_LLAVE


def resumen_clave(usuario):
    """Parte del SHA-256 del hash de la contraseña: cambia cuando cambia la contraseña, y no la revela."""
    return hashlib.sha256(usuario.password.encode()).hexdigest()[:16]


def emitir_llave(usuario, vence=None):
    """Llave nueva. `vence` (epoch) conserva el vencimiento de la llave anterior al canjearla."""
    llave = LlaveDispositivo.for_user(usuario)
    llave[CLAIM_SOLO_LECTURA] = True
    llave[CLAIM_CLAVE] = resumen_clave(usuario)
    if vence is not None:
        llave['exp'] = vence
    return llave
