import {
  Acceso,
  Activo,
  EstadoSensor,
  Intervencion,
  NivelAmbiental,
  Umbrales,
  Usuario,
} from '../models';

/**
 * Datos de demostracion para trabajar el frontend sin el API.
 * Se eliminan cuando `environment.usarDatosSimulados` pase a false.
 */

const ahora = () => new Date();

/** Devuelve una fecha ISO desplazada hacia atras en minutos. */
function haceMinutos(minutos: number): string {
  const d = ahora();
  d.setMinutes(d.getMinutes() - minutos);
  return d.toISOString();
}

function haceDias(dias: number): string {
  const d = ahora();
  d.setDate(d.getDate() - dias);
  return d.toISOString();
}

export const UMBRALES: Umbrales = {
  temperaturaAdvertencia: 24,
  temperaturaCritica: 27,
  humedadMinima: 35,
  humedadMaxima: 60,
};

export function nivelPorLectura(temperatura: number, humedad: number): NivelAmbiental {
  if (
    temperatura >= UMBRALES.temperaturaCritica ||
    humedad < UMBRALES.humedadMinima ||
    humedad > UMBRALES.humedadMaxima
  ) {
    return 'critico';
  }
  if (temperatura >= UMBRALES.temperaturaAdvertencia) {
    return 'advertencia';
  }
  return 'normal';
}

export const USUARIOS_DEMO: Array<Usuario & { clave: string }> = [
  { id: 1, nombre: 'Fidel Rodriguez', correo: 'admin@sicma.cl', rol: 'administrador', clave: 'sicma2026' },
  { id: 2, nombre: 'Alvaro Gonzalez', correo: 'tecnico@sicma.cl', rol: 'tecnico', clave: 'sicma2026' },
  { id: 3, nombre: 'Claudio Varas', correo: 'jefatura@sicma.cl', rol: 'jefatura', clave: 'sicma2026' },
];

export const ACTIVOS: Activo[] = [
  { id: 1, codigo: 'ACT-0001', nombre: 'Host de virtualizacion 01', tipo: 'servidor', marca: 'Dell', modelo: 'PowerEdge R650', numeroSerie: 'DLL-R650-1182', sitio: 'A', rack: 'A1', unidadRack: 12, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2024-03-11', ultimaIntervencion: haceDias(14) },
  { id: 2, codigo: 'ACT-0002', nombre: 'Host de virtualizacion 02', tipo: 'servidor', marca: 'Dell', modelo: 'PowerEdge R650', numeroSerie: 'DLL-R650-1183', sitio: 'A', rack: 'A1', unidadRack: 14, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2024-03-11', ultimaIntervencion: haceDias(14) },
  { id: 3, codigo: 'ACT-0003', nombre: 'Switch de acceso A1', tipo: 'switch', marca: 'Cisco', modelo: 'Catalyst 9200', numeroSerie: 'CSC-9200-4471', sitio: 'A', rack: 'A1', unidadRack: 42, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2023-08-02' },
  { id: 4, codigo: 'ACT-0004', nombre: 'Almacenamiento compartido', tipo: 'almacenamiento', marca: 'Synology', modelo: 'RS3621xs+', numeroSerie: 'SYN-3621-0098', sitio: 'A', rack: 'A1', unidadRack: 30, estado: 'operativo', responsable: 'Fidel Rodriguez', fechaAdquisicion: '2024-01-20', ultimaIntervencion: haceDias(41) },
  { id: 5, codigo: 'ACT-0005', nombre: 'SAI sala principal', tipo: 'sai', marca: 'APC', modelo: 'Smart-UPS SRT 5000', numeroSerie: 'APC-SRT-7712', sitio: 'A', rack: 'A1', unidadRack: 2, estado: 'en mantencion', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2022-11-05', ultimaIntervencion: haceDias(2) },
  { id: 6, codigo: 'ACT-0006', nombre: 'Router de borde', tipo: 'router', marca: 'MikroTik', modelo: 'CCR2004', numeroSerie: 'MKT-2004-3310', sitio: 'A', rack: 'A1', unidadRack: 40, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2023-05-17' },
  { id: 7, codigo: 'ACT-0007', nombre: 'Nodo sensor pasillo frio', tipo: 'sensor', marca: 'Espressif', modelo: 'ESP32-S3 + DHT22', numeroSerie: 'ESP-S3-0001', sitio: 'A', rack: 'A1', unidadRack: 20, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2025-07-30' },
  { id: 8, codigo: 'ACT-0008', nombre: 'Nodo sensor pasillo caliente', tipo: 'sensor', marca: 'Espressif', modelo: 'ESP32-S3 + DHT22', numeroSerie: 'ESP-S3-0002', sitio: 'A', rack: 'A2', unidadRack: 20, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2025-07-30' },
  { id: 9, codigo: 'ACT-0009', nombre: 'Host de virtualizacion 03', tipo: 'servidor', marca: 'HPE', modelo: 'ProLiant DL360', numeroSerie: 'HPE-DL360-2290', sitio: 'B', rack: 'B1', unidadRack: 10, estado: 'operativo', responsable: 'Fidel Rodriguez', fechaAdquisicion: '2024-09-08' },
  { id: 10, codigo: 'ACT-0010', nombre: 'Switch de acceso B1', tipo: 'switch', marca: 'Cisco', modelo: 'Catalyst 9200', numeroSerie: 'CSC-9200-4472', sitio: 'B', rack: 'B1', unidadRack: 42, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2023-08-02' },
  { id: 11, codigo: 'ACT-0011', nombre: 'Almacenamiento de replica', tipo: 'almacenamiento', marca: 'Synology', modelo: 'RS2421+', numeroSerie: 'SYN-2421-0455', sitio: 'B', rack: 'B1', unidadRack: 28, estado: 'en falla', responsable: 'Fidel Rodriguez', fechaAdquisicion: '2024-01-20', ultimaIntervencion: haceDias(1) },
  { id: 12, codigo: 'ACT-0012', nombre: 'SAI sala contingencia', tipo: 'sai', marca: 'APC', modelo: 'Smart-UPS SRT 3000', numeroSerie: 'APC-SRT-7788', sitio: 'B', rack: 'B1', unidadRack: 2, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2022-11-05' },
  { id: 13, codigo: 'ACT-0013', nombre: 'Servidor de respaldo antiguo', tipo: 'servidor', marca: 'Dell', modelo: 'PowerEdge R430', numeroSerie: 'DLL-R430-0021', sitio: 'B', rack: 'B1', unidadRack: 36, estado: 'de baja', responsable: 'Claudio Varas', fechaAdquisicion: '2018-04-12', ultimaIntervencion: haceDias(120) },
  { id: 14, codigo: 'ACT-0014', nombre: 'Lector biometrico puerta principal', tipo: 'otro', marca: 'ZKTeco', modelo: 'SpeedFace V5L', numeroSerie: 'ZKT-V5L-6640', sitio: 'A', rack: 'sin rack', unidadRack: 0, estado: 'operativo', responsable: 'Alvaro Gonzalez', fechaAdquisicion: '2025-06-14' },
];

function serieTemperatura(base: number): number[] {
  return Array.from({ length: 12 }, (_, i) =>
    Number((base + Math.sin(i / 2) * 0.8 + (i > 8 ? (i - 8) * 0.25 : 0)).toFixed(1)),
  );
}

function construirSensor(
  sensorId: string,
  ubicacion: string,
  sitio: 'A' | 'B',
  rack: string,
  temperatura: number,
  humedad: number,
  minutos: number,
): EstadoSensor {
  return {
    sensorId,
    ubicacion,
    sitio,
    rack,
    temperatura,
    humedad,
    nivel: nivelPorLectura(temperatura, humedad),
    actualizadoEn: haceMinutos(minutos),
    historial: serieTemperatura(temperatura - 0.9),
  };
}

export const SENSORES: EstadoSensor[] = [
  construirSensor('ESP-S3-0001', 'Pasillo frio', 'A', 'A1', 21.4, 47, 0),
  construirSensor('ESP-S3-0002', 'Pasillo caliente', 'A', 'A2', 25.8, 44, 0),
  construirSensor('ESP-S3-0003', 'Sala UPS', 'A', 'A1', 27.9, 41, 1),
  construirSensor('ESP-S3-0004', 'Rack de red', 'A', 'A3', 22.7, 52, 0),
  construirSensor('ESP-S3-0005', 'Sala contingencia', 'B', 'B1', 20.9, 58, 1),
  construirSensor('ESP-S3-0006', 'Bodega de equipos', 'B', 'B2', 23.1, 33, 2),
];

export const ACCESOS: Acceso[] = [
  { id: 1, persona: 'Alvaro Gonzalez', rol: 'Administrador de infraestructura', metodo: 'biometrico', movimiento: 'entrada', puerta: 'Puerta principal', sitio: 'A', resultado: 'autorizado', registradoEn: haceMinutos(18) },
  { id: 2, persona: 'Fidel Rodriguez', rol: 'Desarrollo e integracion', metodo: 'biometrico', movimiento: 'entrada', puerta: 'Puerta principal', sitio: 'A', resultado: 'autorizado', registradoEn: haceMinutos(96) },
  { id: 3, persona: 'Desconocido', rol: 'Sin registro', metodo: 'biometrico', movimiento: 'entrada', puerta: 'Puerta principal', sitio: 'A', resultado: 'denegado', motivo: 'Huella no reconocida', registradoEn: haceMinutos(133) },
  { id: 4, persona: 'Claudio Varas', rol: 'Coordinacion de pruebas', metodo: 'tarjeta', movimiento: 'entrada', puerta: 'Puerta lateral', sitio: 'A', resultado: 'autorizado', registradoEn: haceMinutos(190) },
  { id: 5, persona: 'Alvaro Gonzalez', rol: 'Administrador de infraestructura', metodo: 'biometrico', movimiento: 'salida', puerta: 'Puerta principal', sitio: 'A', resultado: 'autorizado', registradoEn: haceMinutos(240) },
  { id: 6, persona: 'Proveedor SAI', rol: 'Servicio externo', metodo: 'manual', movimiento: 'entrada', puerta: 'Puerta principal', sitio: 'A', resultado: 'autorizado', motivo: 'Autorizado por jefatura', registradoEn: haceMinutos(300) },
  { id: 7, persona: 'Proveedor SAI', rol: 'Servicio externo', metodo: 'manual', movimiento: 'entrada', puerta: 'Sala contingencia', sitio: 'B', resultado: 'denegado', motivo: 'Fuera de horario autorizado', registradoEn: haceMinutos(370) },
  { id: 8, persona: 'Fidel Rodriguez', rol: 'Desarrollo e integracion', metodo: 'biometrico', movimiento: 'salida', puerta: 'Puerta principal', sitio: 'A', resultado: 'autorizado', registradoEn: haceMinutos(1420) },
];

export const INTERVENCIONES: Intervencion[] = [
  { id: 1, folio: 'INT-0031', activoId: 11, activoCodigo: 'ACT-0011', tipo: 'correctiva', descripcion: 'Disco 3 del arreglo marca falla. Se solicita repuesto al proveedor.', tecnico: 'Alvaro Gonzalez', estado: 'en curso', iniciadaEn: haceDias(1) },
  { id: 2, folio: 'INT-0030', activoId: 5, activoCodigo: 'ACT-0005', tipo: 'preventiva', descripcion: 'Cambio programado de banco de baterias del SAI.', tecnico: 'Alvaro Gonzalez', estado: 'en curso', iniciadaEn: haceDias(2) },
  { id: 3, folio: 'INT-0029', activoId: 7, activoCodigo: 'ACT-0007', tipo: 'instalacion', descripcion: 'Montaje del nodo sensor en pasillo frio y calibracion inicial.', tecnico: 'Fidel Rodriguez', estado: 'cerrada', iniciadaEn: haceDias(9), cerradaEn: haceDias(9) },
  { id: 4, folio: 'INT-0028', activoId: 1, activoCodigo: 'ACT-0001', tipo: 'preventiva', descripcion: 'Limpieza de ventiladores y actualizacion de firmware.', tecnico: 'Alvaro Gonzalez', estado: 'cerrada', iniciadaEn: haceDias(14), cerradaEn: haceDias(14) },
  { id: 5, folio: 'INT-0027', activoId: 13, activoCodigo: 'ACT-0013', tipo: 'retiro', descripcion: 'Baja del servidor y borrado seguro de discos.', tecnico: 'Claudio Varas', estado: 'cerrada', iniciadaEn: haceDias(120), cerradaEn: haceDias(119) },
  { id: 6, folio: 'INT-0032', activoId: 4, activoCodigo: 'ACT-0004', tipo: 'preventiva', descripcion: 'Revision de estado del arreglo y prueba de restauracion.', tecnico: 'Fidel Rodriguez', estado: 'planificada', iniciadaEn: haceDias(-3) },
];
