/**
 * App móvil (Capacitor, RF-PLT-02): solo consulta.
 *
 * Se compila con `npx ng build --configuration movil`. La app no tiene un servidor propio,
 * así que la API va con URL absoluta: el backend publicado por Cloudflare Tunnel.
 */
export const environment = {
  production: true,
  apiUrl: 'https://api.sicma.cl/api',
  usarDatosSimulados: false,
  /** Oculta toda acción y pide al backend tokens de solo lectura (canal "movil"). */
  soloConsulta: true,
  refrescoMonitoreoMs: 30_000,
  refrescoInfraestructuraMs: 60_000,
};
