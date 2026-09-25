export const environment = {
  production: true,
  apiUrl: '/api',
  /**
   * Se mantiene en true para que la demostracion y el APK funcionen sin backend.
   * Ponerlo en false apenas el API Django este publicado: no hay que tocar nada mas.
   */
  usarDatosSimulados: true,
  refrescoMonitoreoMs: 30_000,
};
