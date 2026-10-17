/** Modelos de dominio de SICMA. Deben reflejar el modelo de datos de la base. */

export type Sitio = 'A' | 'B';

// ---------------------------------------------------------------- Usuarios

export type RolUsuario =
  | 'administrador'
  | 'administradorprivilegiado'
  | 'tecnico'
  | 'jefatura'
  | 'auditor';

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  rol: RolUsuario;
  inactivityTimeoutMinutes: number;
}

export type RolGestion = 'Administrador' | 'AdministradorPrivilegiado' | 'Jefatura' | 'Tecnico' | 'Auditor';

export interface UsuarioGestion {
  id: number;
  username: string;
  nombre: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  rol: string | null;
  inactivity_timeout_minutes: number;
  password_never_expires: boolean;
  password_changed_at: string;
  /** null si la contraseña no expira (cuenta exenta o política en 0). */
  password_expires_at: string | null;
  password_expired: boolean;
}

/** Política global de contraseñas. max_age_days = 0 significa sin expiración. */
export interface PoliticaContrasenas {
  max_age_days: number;
}

export interface SesionIniciada {
  usuario: Usuario;
  token: string;
  refreshToken: string;
}

// ------------------------------------------------- Inventario y catálogos

/** Estados del ciclo de vida de un activo (enum de la tabla activo). 'Retirado' = dado de baja. */
export type EstadoInventario = 'Operativo' | 'Degradado' | 'En_mantenimiento' | 'Fuera_de_servicio' | 'Retirado';
export type Criticidad = 'Baja' | 'Media' | 'Alta' | 'Critica';

/** Activo del inventario de SICMA (RF-ACT). */
export interface ActivoInventario {
  id: number;
  codigo: string;
  nombre: string;
  tipo: string | null;
  marca: string | null;
  modelo: string | null;
  numero_serie: string;
  estado: EstadoInventario;
  criticidad: Criticidad;
  ubicacion: number;
  ubicacion_nombre: string;
  responsable: number | null;
  responsable_nombre: string | null;
  responsable_email: string | null;
  fecha_alta: string;
  observaciones: string | null;
}

export interface HistorialActivo {
  id: number;
  /** 'alta' o el nombre del campo modificado. */
  campo_modificado: string;
  valor_anterior: string | null;
  valor_nuevo: string | null;
  usuario_nombre: string;
  fecha_hora: string;
}

export interface TipoActivoCatalogo {
  id: number;
  nombre: string;
  activo: boolean;
}

export interface UbicacionCatalogo {
  id: number;
  sala: string;
  zona: string | null;
  rack: string | null;
  posicion: string | null;
  ubicacion_padre_id: number | null;
  activa: boolean;
}

export interface SensorCatalogo {
  id: number;
  codigo: string;
  tipo: string;
  estado: 'Activo' | 'Inactivo';
  intervalo_esperado_segundos: number;
  ubicacion: UbicacionCatalogo;
  ultima_medicion: { temperatura: string | null; humedad: string | null; fecha_hora_medicion: string } | null;
}

export interface UsuarioResumen {
  id: number;
  nombre: string;
  email: string | null;
}

// ------------------------------------------------- Equipos en Zabbix

export type TipoActivo =
  | 'servidor'
  | 'switch'
  | 'router'
  | 'almacenamiento'
  | 'sai'
  | 'sensor'
  | 'otro';

export type EstadoActivo = 'operativo' | 'en mantencion' | 'en falla' | 'de baja';

/** Host monitoreado por Zabbix (/api/infraestructura/activos/). Se cruza con el inventario por código. */
export interface Activo {
  id: number;
  codigo: string;
  nombre: string;
  tipo: TipoActivo;
  estado: EstadoActivo;
  grupo?: string[];
  direccion?: string;
  puerto?: number | null;
  mantenimiento?: boolean;
  problemasActivos?: number;
  mysqlGrupoOnline?: boolean | null;
  mysqlEsPrimario?: boolean | null;
  ultimoError?: string | null;
  /** Campos heredados del catálogo de activos local, no enviados por Zabbix. */
  marca?: string;
  modelo?: string;
  numeroSerie?: string;
  sitio?: Sitio;
  rack?: string;
  unidadRack?: number;
  responsable?: string;
  fechaAdquisicion?: string;
  ultimaIntervencion?: string;
}

/** Problema registrado por Zabbix en un servidor (RF-INF-03). */
export interface EventoTecnico {
  evento_id: string;
  problema: string;
  severidad: string;
  /** 0 = no clasificado … 5 = desastre. */
  severidad_num: number;
  inicio: string;
  fin: string | null;
  estado: 'activo' | 'resuelto';
  duracion_segundos: number | null;
  reconocido: boolean;
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
  /** Umbrales vigentes de la zona del sensor; null si la zona no tiene ninguno definido. */
  umbrales: Umbrales | null;
  /** Por qué la lectura está fuera de rango (vacío si está normal). */
  motivos: string[];
}

/** Rango permitido por variable (RF-AMB-03). null = no definido para esa variable. */
export interface Umbrales {
  temperaturaMinima: number | null;
  temperaturaMaxima: number | null;
  humedadMinima: number | null;
  humedadMaxima: number | null;
}

/** Umbrales vigentes de una zona (ubicación) del datacenter. */
export interface UmbralZona extends Umbrales {
  ubicacionId: number;
  nombre: string;
  /** Responsables de alerta de la zona: reciben el correo (RF-CAT-05 / RF-AMB-05). */
  correos: string[];
}

/** Alerta generada por SICMA (RF-AMB-04). */
export interface Alerta {
  id: number;
  origen: 'IoT' | 'Biometria' | 'Zabbix';
  condicion: string;
  severidad: 'Informativa' | 'Advertencia' | 'Alta' | 'Critica';
  estado: 'Nueva' | 'Reconocida' | 'Cerrada';
  fecha_apertura: string;
  contador_ocurrencias: number;
  fecha_ultima_ocurrencia: string | null;
  sensor_codigo: string | null;
  ubicacion: number | null;
  /** event_id de Zabbix, solo en alertas de origen Zabbix (RF-INF-02). */
  evento_zabbix: string | null;
}

// --------------------------------------------------------------- Arduinos

export interface Arduino {
  id: string;
  nombre: string;
  ubicacion: string;
  sitio: Sitio;
  rack: string;
  estado: 'conectado' | 'desconectado';
  ultimaLectura: string;
  temperatura: number;
  humedad: number;
  /** Umbrales de la zona donde está instalado (se definen en Monitoreo). */
  umbrales: Umbrales | null;
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
