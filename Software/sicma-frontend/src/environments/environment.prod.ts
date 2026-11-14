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
  /**
   * Enlace prellenado del Microsoft Forms de solicitudes de intervención (botón "Nueva intervención"
   * de la ficha de activo). En Forms: "Obtener vínculo rellenado previamente", escribir {rack} en
   * "Rack a intervenir" (y {activo} donde corresponda) y pegar aquí el vínculo. Vacío = sin botón.
   */
  formularioIntervencionUrl: '',
};
