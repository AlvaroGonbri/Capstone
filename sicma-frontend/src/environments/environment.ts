/**
 * Configuracion de entorno para desarrollo.
 *
 * Mientras el API Django no este disponible, `usarDatosSimulados` mantiene la
 * aplicacion funcionando contra los datos de `core/mock`. Cuando el backend
 * este listo basta con ponerlo en false: los servicios ya hacen la llamada HTTP.
 */
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api',
  usarDatosSimulados: true,
  /** Periodo de refresco del panel de monitoreo, en milisegundos. */
  refrescoMonitoreoMs: 30_000,
};
