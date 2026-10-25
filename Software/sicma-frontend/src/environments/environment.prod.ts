/**
 * Web publicada en Cloudflare Pages (https://app.sicma.cl).
 *
 * La web y la API están en dominios distintos, así que la API va con URL absoluta:
 * el backend on-premise publicado por Cloudflare Tunnel.
 */
export const environment = {
  production: true,
  apiUrl: 'https://api.sicma.cl/api',
  usarDatosSimulados: false,
  soloConsulta: false,
  refrescoMonitoreoMs: 10_000,
  refrescoInfraestructuraMs: 60_000,
};
