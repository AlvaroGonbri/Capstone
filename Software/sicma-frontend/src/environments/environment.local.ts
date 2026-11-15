/**
 * Web en la red local, para validarla antes de publicarla en Cloudflare Pages (`npm run web-local`).
 *
 * La sirve `Software/servir_web_local.py` desde el PC del backend, que además reenvía /api/ a la
 * API (puerto 8000). La web y la API quedan en la misma dirección: la API va relativa, así no
 * depende de la IP del PC ni necesita CORS. Compila en dist/sicma-frontend-local (no pisa el de Pages).
 */
export const environment = {
  production: true,
  apiUrl: '/api',
  usarDatosSimulados: false,
  soloConsulta: false,
  refrescoMonitoreoMs: 10_000,
  refrescoInfraestructuraMs: 60_000,
  /** Igual que en environment.prod.ts: vacío = sin botón "Nueva intervención". */
  formularioIntervencionUrl: '',
};
