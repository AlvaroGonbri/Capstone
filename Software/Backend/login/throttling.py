from rest_framework.throttling import ScopedRateThrottle


# Desde aquí llega el túnel de Cloudflare (cloudflared corre en este mismo equipo).
ORIGENES_DEL_TUNEL = {'127.0.0.1', '::1'}


class ScopedRateThrottleClienteReal(ScopedRateThrottle):
    """Limita por la IP real del cliente.

    DRF, por defecto, identifica al cliente con X-Forwarded-For, que el atacante puede escribir
    a su gusto para saltarse el límite. Detrás del túnel todas las peticiones vienen de 127.0.0.1;
    la IP real la pone Cloudflare en CF-Connecting-IP (no se puede falsificar pasando por él), y
    solo se le cree cuando la petición viene del túnel. En la red local se usa la IP de conexión.
    """

    def get_ident(self, request):
        remoto = request.META.get('REMOTE_ADDR', '')
        if remoto in ORIGENES_DEL_TUNEL:
            return request.META.get('HTTP_CF_CONNECTING_IP', '').strip() or remoto
        return remoto
