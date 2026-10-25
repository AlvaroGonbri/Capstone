/** Modelos de dominio de SICMA. Deben reflejar el modelo de datos de la base. */

export type Sitio = 'A' | 'B';

// ---------------------------------------------------------------- Usuarios

export type RolUsuario =
  | 'administrador'
  | 'administradorprivilegiado'
  | 'tecnico'
  | 'jefatura'
  | 'auditor'
  /** Departamento de contratistas: solo enrola y habilita al personal externo. */
  | 'contratistas';

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  rol: RolUsuario;
  inactivityTimeoutMinutes: number;
}

export type RolGestion = 'Administrador' | 'AdministradorPrivilegiado' | 'Jefatura' | 'Tecnico' | 'Auditor' | 'Contratistas';

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

/** Nombre de un estado del catálogo de estados de activo (RF-CAT-03). 'Retirado' = dado de baja. */
export type EstadoInventario = string;
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

/** Estado de activo del catálogo. Los de sistema (Operativo, Retirado) no se desactivan. */
export interface EstadoActivoCatalogo {
  id: number;
  nombre: string;
  etiqueta: string;
  color: string;
  activo: boolean;
  es_sistema: boolean;
  orden: number;
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
  /** Última acción manual: quién la reconoció o cerró, cuándo y con qué comentario. */
  ultima_gestion: { accion: 'Reconocida' | 'Cerrada'; usuario: string | null; comentario: string; fecha_hora: string } | null;
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

/** Resultado de un intento de acceso (tabla evento_acceso). */
export type ResultadoAcceso = 'Permitido' | 'Denegado' | 'Error';
export type EstadoRegistro = 'Activo' | 'Inactivo';
export type DiaSemana = 'Lun' | 'Mar' | 'Mie' | 'Jue' | 'Vie' | 'Sab' | 'Dom';

/** Intento de acceso registrado por el agente del lector (RF-ACC-01). Nunca incluye la huella. */
export interface EventoAcceso {
  id: number;
  fecha_hora: string;
  resultado: ResultadoAcceso;
  motivo: string | null;
  identificador_biometrico_externo: string;
  persona: number | null;
  persona_nombre: string | null;
  punto_acceso: number;
  punto_nombre: string;
  ubicacion_nombre: string;
}

export type EstadoEnrolamiento = 'Pendiente' | 'EnCurso' | 'Completada' | 'Fallida' | 'Cancelada';

/** Pedido al agente del lector para capturar una huella (el navegador no puede usar el lector USB). */
export interface SolicitudEnrolamiento {
  id: number;
  persona: number;
  punto_acceso: number;
  punto_nombre: string;
  estado: EstadoEnrolamiento;
  mensaje: string;
  solicitada_por_nombre: string | null;
  fecha_solicitud: string;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  /** Lo que pide el agente en este momento, para guiar a la persona frente al lector. */
  muestra: number;
  total_muestras: number;
  indicacion: string;
}

/** Persona que puede entrar, asociada a su identificador de huella (RF-ACC-02). */
export interface PersonaAutorizada {
  id: number;
  nombre: string;
  rut: string | null;
  empresa: string | null;
  identificador_biometrico_externo: string;
  /** Activo = habilitada para trabajar en el datacenter (lo decide el Departamento de contratistas). */
  estado: EstadoRegistro;
  usuario: number | null;
  usuario_nombre: string | null;
  huella_registrada_en: string | null;
  huella_registrada_por_nombre: string | null;
  enrolamiento: SolicitudEnrolamiento | null;
}

/** Alta o baja manual de una persona, con su motivo (historial). */
export interface CambioHabilitacion {
  habilitada: boolean;
  motivo: string;
  usuario_nombre: string | null;
  fecha_hora: string;
}

/** Lector biométrico. Su agente se autentica con una clave que solo se muestra al crearla. */
export interface PuntoAcceso {
  id: number;
  nombre: string;
  ubicacion: number;
  ubicacion_nombre: string;
  estado: EstadoRegistro;
  tiene_clave: boolean;
}

export interface VentanaPermiso {
  dia_semana: DiaSemana;
  hora_inicio: string;
  hora_fin: string;
}

/** Permiso de una persona en un punto. Sin ventanas = todo el día, todos los días. */
export interface PermisoAcceso {
  id: number;
  persona: number;
  persona_nombre: string;
  punto_acceso: number;
  punto_nombre: string;
  vigencia_inicio: string;
  vigencia_fin: string | null;
  estado: 'Activo' | 'Revocado';
  dias: VentanaPermiso[];
}

// ---------------------------------------------------------- Intervenciones

/** Ciclo de vida de una intervención (tabla intervencion). */
export type EstadoIntervencion =
  | 'Pendiente'
  | 'CambiosSolicitados'
  | 'Aprobada'
  | 'Rechazada'
  | 'EnEjecucion'
  | 'Ejecutada'
  | 'Fallida'
  | 'Cancelada';

export interface DecisionIntervencion {
  decision: 'Aprobada' | 'Rechazada';
  decisor_correo: string | null;
  decisor_nombre: string | null;
  observacion: string | null;
  fecha_hora: string;
}

/** Intervención solicitada por Forms, aprobada en Teams y ejecutada en SICMA (RF-INT). */
export interface Intervencion {
  id: number;
  objetivo: string;
  descripcion: string | null;
  /** Servicios afectados que indicó el solicitante. */
  impacto_esperado: string | null;
  plan_reversa: string | null;
  rack: string | null;
  solicitante_nombre: string | null;
  solicitante_correo: string | null;
  estado: EstadoIntervencion;
  fecha_solicitud: string | null;
  fecha_inicio: string | null;
  fecha_termino: string | null;
  fecha_cierre: string | null;
  observacion_cierre: string | null;
  responsable: number | null;
  responsable_nombre: string | null;
  activos: Array<{ id: number; codigo: string; nombre: string }>;
  decisiones: DecisionIntervencion[];
  /** SICMA ya pidió al flujo de Power Automate crear la cita en Outlook. */
  agenda_enviada: boolean;
  personal_externo: PersonalIntervencion[];
}

/** Persona externa que trabajará en la intervención, con su estado actual. */
export interface PersonalIntervencion {
  id: number;
  nombre: string;
  rut: string | null;
  empresa: string | null;
  identificador: string;
  habilitada: boolean;
  huella_registrada: boolean;
  /** Huella verificada al iniciar la intervención (demuestra que es quien fue asignado). */
  verificada_en: string | null;
  verificacion: SolicitudVerificacion | null;
}

/** Pedido al lector para confirmar la identidad de UNA persona con su huella. */
export interface SolicitudVerificacion {
  id: number;
  persona: number;
  intervencion_id: number | null;
  punto_acceso: number;
  punto_nombre: string;
  estado: 'Pendiente' | 'EnCurso' | 'Completada' | 'Fallida' | 'Cancelada';
  mensaje: string;
  identificado: string;
  intento: number;
  total_intentos: number;
  indicacion: string;
  fecha_solicitud: string;
  fecha_fin: string | null;
}

export interface TecnicoAsignable {
  id: number;
  nombre: string;
  email: string | null;
  rol: RolUsuario;
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

/** Estado de la consulta periódica a Zabbix que hace el backend (RF-INF-01). */
export interface SincronizacionZabbix {
  intervalo_segundos: number;
  ultimo_intento: string | null;
  ultima_exitosa: string | null;
  /** false si la última consulta exitosa tiene más de 3 intervalos: el proceso no corre o Zabbix falla. */
  al_dia: boolean;
  error: string | null;
}
