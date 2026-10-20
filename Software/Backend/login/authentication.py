from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication


# Claim que marca los tokens emitidos a la app móvil (RF-PLT-02: solo consulta).
CLAIM_SOLO_LECTURA = 'solo_lectura'
# Escrituras que la app sí necesita para mantener la sesión.
VISTAS_PERMITIDAS_SOLO_LECTURA = {'logout', 'activity'}


class SicmaJWTAuthentication(JWTAuthentication):
    """JWT de SICMA. Un token de solo lectura no puede modificar nada, sea cual sea su rol.

    La app móvil oculta los botones de acción, pero la protección real está aquí: aunque alguien
    use el token de la app para llamar a la API directamente, el backend rechaza la escritura.
    """

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is None:
            return None
        _, token = resultado
        if token.get(CLAIM_SOLO_LECTURA) and request.method not in SAFE_METHODS:
            vista = getattr(getattr(request, 'resolver_match', None), 'url_name', None)
            if vista not in VISTAS_PERMITIDAS_SOLO_LECTURA:
                raise PermissionDenied('La aplicación móvil es solo de consulta. Usa la versión web para hacer cambios.')
        return resultado
