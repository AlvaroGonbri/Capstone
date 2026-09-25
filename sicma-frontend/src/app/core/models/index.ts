/** Modelos de dominio de SICMA. Deben reflejar el modelo de datos de la base. */

export type Sitio = 'A' | 'B';

// ---------------------------------------------------------------- Usuarios

export type RolUsuario = 'administrador' | 'tecnico' | 'jefatura';

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  rol: RolUsuario;
}

export interface SesionIniciada {
  usuario: Usuario;
  token: string;
}

// ----------------------------------------------------------------- Activos

export type TipoActivo =
  | 'servidor'
  | 'switch'
  | 'router'
  | 'almacenamiento'
  | 'sai'
  | 'sensor'
  | 'otro';

export type EstadoActivo = 'operativo' | 'en mantencion' | 'en falla' | 'de baja';

export interface Activo {
  id: number;
  codigo: string;
  nombre: string;
  tipo: TipoActivo;
  marca: string;
  modelo: string;
  numeroSerie: string;
  sitio: Sitio;
  rack: string;
  unidadRack: number;
  estado: EstadoActivo;
  responsable: string;
  fechaAdquisicion: string;
  ultimaIntervencion?: string;
}

// -------------------------------------------------- Monitoreo ambiental

export type NivelAmbiental = 'normal' | 'advertencia' | 'critico';

export interface Lectura {
  id: number;
  sensorId: string;
  temperatura: number;
  humedad: number;
  registradoEn: string;
}

export interface EstadoSensor {
  sensorId: string;
  ubicacion: string;
  sitio: Sitio;
  rack: string;
  temperatura: number;
  humedad: number;
  nivel: NivelAmbiental;
  actualizadoEn: string;
  /** Ultimas lecturas de temperatura, de la mas antigua a la mas reciente. */
  historial: number[];
}

export interface Umbrales {
  temperaturaAdvertencia: number;
  temperaturaCritica: number;
  humedadMinima: number;
  humedadMaxima: number;
}

// ----------------------------------------------------------------- Accesos

export type MetodoAcceso = 'biometrico' | 'tarjeta' | 'manual';
export type ResultadoAcceso = 'autorizado' | 'denegado';

export interface Acceso {
  id: number;
  persona: string;
  rol: string;
  metodo: MetodoAcceso;
  movimiento: 'entrada' | 'salida';
  puerta: string;
  sitio: Sitio;
  resultado: ResultadoAcceso;
  motivo?: string;
  registradoEn: string;
}

// ---------------------------------------------------------- Intervenciones

export type TipoIntervencion = 'preventiva' | 'correctiva' | 'instalacion' | 'retiro';
export type EstadoIntervencion = 'planificada' | 'en curso' | 'cerrada';

export interface Intervencion {
  id: number;
  folio: string;
  activoId: number;
  activoCodigo: string;
  tipo: TipoIntervencion;
  descripcion: string;
  tecnico: string;
  estado: EstadoIntervencion;
  iniciadaEn: string;
  cerradaEn?: string;
}

// ------------------------------------------------------------------ Panel

export interface ResumenPanel {
  activosTotales: number;
  activosOperativos: number;
  activosEnFalla: number;
  sensoresEnAlerta: number;
  accesosHoy: number;
  accesosDenegadosHoy: number;
  intervencionesAbiertas: number;
}
