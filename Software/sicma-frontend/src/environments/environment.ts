/**
 * Configuracion de entorno para desarrollo.
 *
 * Mientras el API Django no este disponible, `usarDatosSimulados` mantiene la
 * aplicacion funcionando contra los datos de `core/mock`. Cuando el backend
 * este listo basta con ponerlo en false: los servicios ya hacen la llamada HTTP.
 */
export const environment = {
  production: false,
  apiUrl: 'http://192.168.100.102:8000/api',
  usarDatosSimulados: false,
  /** true solo en la app móvil (RF-PLT-02): sin acciones, tokens de solo lectura. */
  soloConsulta: false,
  /** Periodo de refresco del panel de monitoreo, en milisegundos. */
  refrescoMonitoreoMs: 30_000,
  /** Refresco del estado de los servidores desde Zabbix (RF-INF-01: cada 1 minuto). */
  refrescoInfraestructuraMs: 60_000,
};
