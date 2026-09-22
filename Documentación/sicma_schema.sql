-- =============================================================================
--  SICMA — Modelo de datos (DDL)
--  Motor        : MySQL 8.x (8.0.x / 8.4 LTS)
--  Almacenamiento: InnoDB (obligatorio en todas las tablas)
--  Charset      : utf8mb4 / utf8mb4_0900_ai_ci
--  Topología    : Compatible con InnoDB Cluster (Group Replication + MySQL Router)
--
--  ALCANCE
--  Este script contiene EXCLUSIVAMENTE las entidades de negocio de SICMA.
--  NO incluye tablas gestionadas por Django (auth_user, auth_group, auth_permission,
--  django_migrations, django_session, django_admin_log, django_content_type, etc.):
--  esas las crea el ORM vía migraciones.
--  Fuera de alcance (no se modelan): auditoría general, respaldo lógico,
--  configuración de parámetros generales e identificación por código QR.
--
--  NOTAS DE COMPATIBILIDAD CON InnoDB CLUSTER / GROUP REPLICATION
--    * Group Replication exige que TODA tabla tenga clave primaria explícita.
--      Todas las tablas de este script definen PK BIGINT UNSIGNED AUTO_INCREMENT.
--    * Solo se usa el motor InnoDB (Group Replication no soporta otros motores
--      transaccionales para datos replicados).
--    * Evitar sentencias no soportadas por GR en tiempo de ejecución (p. ej. CREATE
--      TABLE ... SELECT). Este DDL no las utiliza.
--    * gtid_mode = ON y enforce_gtid_consistency = ON en el clúster: este DDL es
--      compatible (no hay operaciones que violen la consistencia de GTID).
--
--  CONVENCIONES
--    * PK: BIGINT UNSIGNED AUTO_INCREMENT.
--    * Fechas/horas: DATETIME. La aplicación persiste SIEMPRE en UTC (RNF-INT-02).
--      NO se usa TIMESTAMP para evitar conversión automática de zona horaria.
--    * FK: ON DELETE RESTRICT por defecto; CASCADE o SET NULL solo donde se indica.
--    * ENUM según diagrama de clases aprobado.
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Ajustes recomendados de sesión para la creación del esquema
SET @OLD_SQL_MODE = @@SQL_MODE;
SET SQL_MODE = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';

-- (Opcional) Crear/usar la base de datos
-- CREATE DATABASE IF NOT EXISTS sicma
--   DEFAULT CHARACTER SET utf8mb4
--   DEFAULT COLLATE utf8mb4_0900_ai_ci;
-- USE sicma;


-- =============================================================================
-- 1. usuario
-- =============================================================================
CREATE TABLE usuario (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre               VARCHAR(150)    NOT NULL,
    correo               VARCHAR(255)    NOT NULL,
    password_hash        VARCHAR(255)    NOT NULL,
    rol                  ENUM('Administrador','Jefatura','Tecnico','Auditor') NOT NULL,
    estado               ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    fecha_ultimo_acceso  DATETIME        NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuario_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Usuarios de la plataforma SICMA (no confundir con auth_user de Django).';


-- =============================================================================
-- 2. ubicacion  (jerarquía auto-referenciada)
-- =============================================================================
CREATE TABLE ubicacion (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sala                 VARCHAR(100)    NOT NULL,
    zona                 VARCHAR(100)    NULL,
    rack                 VARCHAR(100)    NULL,
    posicion             VARCHAR(100)    NULL,
    ubicacion_padre_id   BIGINT UNSIGNED NULL,
    PRIMARY KEY (id),
    KEY idx_ubicacion_padre (ubicacion_padre_id),
    CONSTRAINT fk_ubicacion_padre
        FOREIGN KEY (ubicacion_padre_id) REFERENCES ubicacion (id)
        ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Ubicaciones físicas jerárquicas (sala/zona/rack/posicion).';


-- =============================================================================
-- 3. activo
-- =============================================================================
CREATE TABLE activo (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo        VARCHAR(50)     NOT NULL,
    nombre        VARCHAR(200)    NOT NULL,
    tipo          VARCHAR(100)    NULL,
    marca         VARCHAR(100)    NULL,
    modelo        VARCHAR(100)    NULL,
    numero_serie  VARCHAR(150)    NOT NULL,
    estado        ENUM('Operativo','Degradado','En_mantenimiento','Fuera_de_servicio','Retirado') NOT NULL DEFAULT 'Operativo',
    criticidad    ENUM('Baja','Media','Alta','Critica') NOT NULL DEFAULT 'Media',
    ubicacion_id  BIGINT UNSIGNED NOT NULL,
    fecha_alta    DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    observaciones TEXT            NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_activo_codigo (codigo),
    UNIQUE KEY uq_activo_numero_serie (numero_serie),
    -- Índices para filtros frecuentes (regla 4)
    KEY idx_activo_estado (estado),
    KEY idx_activo_criticidad (criticidad),
    KEY idx_activo_ubicacion (ubicacion_id),
    KEY idx_activo_estado_criticidad_ubic (estado, criticidad, ubicacion_id),
    CONSTRAINT fk_activo_ubicacion
        FOREIGN KEY (ubicacion_id) REFERENCES ubicacion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Activos gestionados (inventario técnico).';


-- =============================================================================
-- 4. historial_activo   (SOLO INSERCIÓN)
-- =============================================================================
CREATE TABLE historial_activo (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    activo_id        BIGINT UNSIGNED NOT NULL,
    campo_modificado VARCHAR(100)    NOT NULL,
    valor_anterior   TEXT            NULL,
    valor_nuevo      TEXT            NULL,
    usuario_id       BIGINT UNSIGNED NOT NULL,
    fecha_hora       DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_hist_activo (activo_id),
    KEY idx_hist_usuario (usuario_id),
    KEY idx_hist_activo_fecha (activo_id, fecha_hora),
    CONSTRAINT fk_hist_activo
        FOREIGN KEY (activo_id) REFERENCES activo (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_hist_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='SOLO INSERCION (append-only). La capa de acceso a datos DEBE impedir UPDATE/DELETE mediante permisos de la cuenta de aplicacion (GRANT solo INSERT/SELECT); MySQL no bloquea updates por tabla de forma nativa.';


-- =============================================================================
-- 5. archivo_adjunto
-- =============================================================================
CREATE TABLE archivo_adjunto (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    activo_id     BIGINT UNSIGNED NOT NULL,
    nombre_archivo VARCHAR(255)   NOT NULL,
    tipo_mime     ENUM('PDF','PNG','JPG') NOT NULL,
    tamano_bytes  BIGINT UNSIGNED NOT NULL,
    fecha_carga   DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    usuario_id    BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    KEY idx_adjunto_activo (activo_id),
    KEY idx_adjunto_usuario (usuario_id),
    CONSTRAINT fk_adjunto_activo
        FOREIGN KEY (activo_id) REFERENCES activo (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_adjunto_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Archivos adjuntos asociados a un activo.';


-- =============================================================================
-- 6. sensor
-- =============================================================================
CREATE TABLE sensor (
    id                          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo                      VARCHAR(50)     NOT NULL,
    tipo                        VARCHAR(100)    NOT NULL,
    ubicacion_id                BIGINT UNSIGNED NOT NULL,
    estado                      ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    intervalo_esperado_segundos INT UNSIGNED    NOT NULL,
    device_key_hash             VARCHAR(255)    NOT NULL COMMENT 'Hash de la device key; nunca en texto claro.',
    PRIMARY KEY (id),
    UNIQUE KEY uq_sensor_codigo (codigo),
    KEY idx_sensor_ubicacion (ubicacion_id),
    CONSTRAINT fk_sensor_ubicacion
        FOREIGN KEY (ubicacion_id) REFERENCES ubicacion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Sensores IoT ambientales.';


-- =============================================================================
-- 7. medicion   (SOLO INSERCIÓN / INMUTABLE)
--     Ver bloque de particionamiento sugerido al final del script.
-- =============================================================================
CREATE TABLE medicion (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sensor_id            BIGINT UNSIGNED NOT NULL,
    evento_id            CHAR(36)        NOT NULL COMMENT 'UUID del evento para idempotencia.',
    temperatura          DECIMAL(5,2)    NULL,
    humedad              DECIMAL(5,2)    NULL,
    fecha_hora_medicion  DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02). Marca de tiempo del sensor.',
    fecha_hora_recepcion DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02). Marca de tiempo de recepcion.',
    origen               ENUM('Real','Simulado') NOT NULL DEFAULT 'Real',
    PRIMARY KEY (id),
    UNIQUE KEY uq_medicion_sensor_evento (sensor_id, evento_id),
    -- Índices para filtros frecuentes (regla 4)
    KEY idx_medicion_sensor_fecha (sensor_id, fecha_hora_medicion),
    KEY idx_medicion_fecha (fecha_hora_medicion),
    CONSTRAINT fk_medicion_sensor
        FOREIGN KEY (sensor_id) REFERENCES sensor (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='SOLO INSERCION (inmutable). La capa de datos DEBE impedir UPDATE/DELETE via permisos (GRANT solo INSERT/SELECT). Idempotencia por UNIQUE(sensor_id, evento_id). Alto volumen: hasta 43.200 registros/sensor/dia -> ver particionamiento sugerido al final.';


-- =============================================================================
-- 8. umbral_ambiental
-- =============================================================================
CREATE TABLE umbral_ambiental (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ubicacion_id  BIGINT UNSIGNED NOT NULL,
    variable      ENUM('Temperatura','Humedad') NOT NULL,
    valor_minimo  DECIMAL(6,2)    NOT NULL,
    valor_maximo  DECIMAL(6,2)    NOT NULL,
    version       INT UNSIGNED    NOT NULL DEFAULT 1,
    vigente_desde DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_umbral_ubicacion (ubicacion_id),
    KEY idx_umbral_ubic_var_version (ubicacion_id, variable, version),
    CONSTRAINT fk_umbral_ubicacion
        FOREIGN KEY (ubicacion_id) REFERENCES ubicacion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Umbrales ambientales versionados por ubicacion y variable.';


-- =============================================================================
-- 9. evento_tecnico_ingesta   (SOLO INSERCIÓN)
-- =============================================================================
CREATE TABLE evento_tecnico_ingesta (
    id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sensor_codigo         VARCHAR(50)     NOT NULL,
    causa                 VARCHAR(255)    NOT NULL,
    contenido_no_sensible JSON            NULL,
    fecha_hora            DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_evt_ingesta_sensor (sensor_codigo),
    KEY idx_evt_ingesta_fecha (fecha_hora)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='SOLO INSERCION. Eventos tecnicos de ingesta (diagnostico). La capa de datos DEBE impedir UPDATE/DELETE via permisos. No se referencia sensor_id por FK a proposito: registra el codigo aunque el sensor no exista aun.';


-- =============================================================================
-- 10. persona_autorizada
-- =============================================================================
CREATE TABLE persona_autorizada (
    id                              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre                          VARCHAR(150)    NOT NULL,
    identificador_biometrico_externo VARCHAR(255)   NOT NULL,
    estado                          ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (id),
    UNIQUE KEY uq_persona_biometrico (identificador_biometrico_externo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Personas autorizadas (identificador biometrico externo, sin datos biometricos crudos).';


-- =============================================================================
-- 11. punto_acceso
-- =============================================================================
CREATE TABLE punto_acceso (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(150)    NOT NULL,
    ubicacion_id BIGINT UNSIGNED NOT NULL,
    estado       ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (id),
    KEY idx_punto_acceso_ubicacion (ubicacion_id),
    CONSTRAINT fk_punto_acceso_ubicacion
        FOREIGN KEY (ubicacion_id) REFERENCES ubicacion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Puntos de acceso fisico controlados por biometria.';


-- =============================================================================
-- 12. permiso_acceso
-- =============================================================================
CREATE TABLE permiso_acceso (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    persona_id       BIGINT UNSIGNED NOT NULL,
    punto_acceso_id  BIGINT UNSIGNED NOT NULL,
    vigencia_inicio  DATE            NOT NULL,
    vigencia_fin     DATE            NULL,
    estado           ENUM('Activo','Revocado') NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (id),
    KEY idx_permiso_persona (persona_id),
    KEY idx_permiso_punto (punto_acceso_id),
    KEY idx_permiso_estado (estado),
    CONSTRAINT fk_permiso_persona
        FOREIGN KEY (persona_id) REFERENCES persona_autorizada (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_permiso_punto
        FOREIGN KEY (punto_acceso_id) REFERENCES punto_acceso (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Permiso de acceso de una persona a un punto de acceso.';


-- =============================================================================
-- 13. permiso_dia   (FK ON DELETE CASCADE)
-- =============================================================================
CREATE TABLE permiso_dia (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    permiso_acceso_id BIGINT UNSIGNED NOT NULL,
    dia_semana        ENUM('Lun','Mar','Mie','Jue','Vie','Sab','Dom') NOT NULL,
    hora_inicio       TIME            NOT NULL,
    hora_fin          TIME            NOT NULL,
    PRIMARY KEY (id),
    KEY idx_permiso_dia_permiso (permiso_acceso_id),
    CONSTRAINT fk_permiso_dia_permiso
        FOREIGN KEY (permiso_acceso_id) REFERENCES permiso_acceso (id)
        ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Ventanas horarias por dia de un permiso de acceso. CASCADE: se elimina con el permiso padre.';


-- =============================================================================
-- 14. evento_acceso   (SOLO INSERCIÓN / INMUTABLE)
-- =============================================================================
CREATE TABLE evento_acceso (
    id                              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    identificador_biometrico_externo VARCHAR(255)   NOT NULL,
    persona_id                      BIGINT UNSIGNED NULL,
    punto_acceso_id                 BIGINT UNSIGNED NOT NULL,
    fecha_hora                      DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    resultado                       ENUM('Permitido','Denegado','Error') NOT NULL,
    motivo                          VARCHAR(255)    NULL,
    PRIMARY KEY (id),
    -- Índices para filtros frecuentes (regla 4)
    KEY idx_evt_acceso_persona (persona_id),
    KEY idx_evt_acceso_punto (punto_acceso_id),
    KEY idx_evt_acceso_fecha (fecha_hora),
    KEY idx_evt_acceso_persona_punto_fecha (persona_id, punto_acceso_id, fecha_hora),
    CONSTRAINT fk_evt_acceso_persona
        FOREIGN KEY (persona_id) REFERENCES persona_autorizada (id)
        ON DELETE SET NULL ON UPDATE RESTRICT,
    CONSTRAINT fk_evt_acceso_punto
        FOREIGN KEY (punto_acceso_id) REFERENCES punto_acceso (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='SOLO INSERCION (inmutable). Registro historico de eventos de acceso. La capa de datos DEBE impedir UPDATE/DELETE via permisos. persona_id NULLABLE + SET NULL: se conserva el evento aunque la persona sea desvinculada.';


-- =============================================================================
-- 15. configuracion_integracion_zabbix
-- =============================================================================
CREATE TABLE configuracion_integracion_zabbix (
    id                             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    url                            VARCHAR(500)    NOT NULL,
    credencial_referencia          VARCHAR(255)    NOT NULL COMMENT 'Referencia a secreto (vault/keyring). NUNCA credencial en texto claro.',
    intervalo_sincronizacion_segundos INT UNSIGNED NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Configuracion de integracion con Zabbix. La credencial se referencia, nunca se almacena en claro.';


-- =============================================================================
-- 16. host_problema_zabbix
-- =============================================================================
CREATE TABLE host_problema_zabbix (
    id                        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    identificador_externo     VARCHAR(255)    NOT NULL,
    activo_id                 BIGINT UNSIGNED NULL,
    disponibilidad            VARCHAR(50)     NULL,
    severidad                 VARCHAR(50)     NULL,
    estado                    VARCHAR(50)     NULL,
    fecha_ultima_sincronizacion DATETIME      NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    UNIQUE KEY uq_hostzbx_identificador (identificador_externo),
    KEY idx_hostzbx_activo (activo_id),
    CONSTRAINT fk_hostzbx_activo
        FOREIGN KEY (activo_id) REFERENCES activo (id)
        ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Hosts/problemas sincronizados desde Zabbix. activo_id NULLABLE + SET NULL: puede desvincularse del activo.';


-- =============================================================================
-- 17. alerta
-- =============================================================================
CREATE TABLE alerta (
    id                       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    origen                   ENUM('IoT','Biometria','Zabbix') NOT NULL,
    condicion                VARCHAR(500)    NOT NULL,
    severidad                ENUM('Informativa','Advertencia','Alta','Critica') NOT NULL,
    estado                   ENUM('Nueva','Reconocida','Cerrada') NOT NULL DEFAULT 'Nueva',
    fecha_apertura           DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    contador_ocurrencias     INT UNSIGNED    NOT NULL DEFAULT 1,
    fecha_ultima_ocurrencia  DATETIME        NULL COMMENT 'UTC (RNF-INT-02)',
    sensor_id                BIGINT UNSIGNED NULL,
    host_problema_zabbix_id  BIGINT UNSIGNED NULL,
    punto_acceso_id          BIGINT UNSIGNED NULL,
    PRIMARY KEY (id),
    -- Índices para filtros frecuentes (regla 4)
    KEY idx_alerta_estado (estado),
    KEY idx_alerta_severidad (severidad),
    KEY idx_alerta_fecha_apertura (fecha_apertura),
    KEY idx_alerta_estado_sev_fecha (estado, severidad, fecha_apertura),
    KEY idx_alerta_sensor (sensor_id),
    KEY idx_alerta_hostzbx (host_problema_zabbix_id),
    KEY idx_alerta_punto (punto_acceso_id),
    CONSTRAINT fk_alerta_sensor
        FOREIGN KEY (sensor_id) REFERENCES sensor (id)
        ON DELETE SET NULL ON UPDATE RESTRICT,
    CONSTRAINT fk_alerta_hostzbx
        FOREIGN KEY (host_problema_zabbix_id) REFERENCES host_problema_zabbix (id)
        ON DELETE SET NULL ON UPDATE RESTRICT,
    CONSTRAINT fk_alerta_punto
        FOREIGN KEY (punto_acceso_id) REFERENCES punto_acceso (id)
        ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Alertas generadas por IoT, Biometria o Zabbix. FKs opcionales SET NULL segun origen.';


-- =============================================================================
-- 18. evidencia_alerta
-- =============================================================================
CREATE TABLE evidencia_alerta (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    alerta_id         BIGINT UNSIGNED NOT NULL,
    causa             VARCHAR(500)    NULL,
    accion_ejecutada  TEXT            NULL,
    resultado         TEXT            NULL,
    usuario_id        BIGINT UNSIGNED NOT NULL,
    fecha_hora        DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_evidencia_alerta (alerta_id),
    KEY idx_evidencia_usuario (usuario_id),
    CONSTRAINT fk_evidencia_alerta
        FOREIGN KEY (alerta_id) REFERENCES alerta (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_evidencia_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Evidencia/gestion de una alerta.';


-- =============================================================================
-- 19. regla_alerta
-- =============================================================================
CREATE TABLE regla_alerta (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    fuente               VARCHAR(100)    NOT NULL,
    condicion            VARCHAR(500)    NOT NULL,
    severidad            ENUM('Informativa','Advertencia','Alta','Critica') NOT NULL,
    destinatarios        JSON            NULL COMMENT 'Lista de destinatarios en JSON. Alternativa normalizada: tabla regla_alerta_destinatario.',
    horario_notificacion VARCHAR(255)    NULL,
    version              INT UNSIGNED    NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    KEY idx_regla_fuente (fuente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Reglas de generacion/enrutamiento de alertas. Destinatarios en JSON (ver alternativa normalizada comentada al final).';


-- =============================================================================
-- 20. intervencion
-- =============================================================================
CREATE TABLE intervencion (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    objetivo          VARCHAR(500)    NOT NULL,
    descripcion       TEXT            NULL,
    impacto_esperado  TEXT            NULL,
    fecha_inicio      DATETIME        NULL COMMENT 'UTC (RNF-INT-02)',
    fecha_termino     DATETIME        NULL COMMENT 'UTC (RNF-INT-02)',
    responsable_id    BIGINT UNSIGNED NOT NULL,
    plan_reversa      TEXT            NULL,
    estado            ENUM('Pendiente','CambiosSolicitados','Aprobada','EnEjecucion','Ejecutada','Fallida','Cancelada') NOT NULL DEFAULT 'Pendiente',
    PRIMARY KEY (id),
    -- Índices para filtros frecuentes (regla 4)
    KEY idx_intervencion_estado (estado),
    KEY idx_intervencion_responsable (responsable_id),
    KEY idx_intervencion_estado_resp (estado, responsable_id),
    CONSTRAINT fk_intervencion_responsable
        FOREIGN KEY (responsable_id) REFERENCES usuario (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Intervenciones/cambios sobre activos (flujo de aprobacion y ejecucion).';


-- =============================================================================
-- 21. notificacion
-- =============================================================================
CREATE TABLE notificacion (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    alerta_id       BIGINT UNSIGNED NULL,
    intervencion_id BIGINT UNSIGNED NULL,
    canal           ENUM('SMTP','PowerAutomate') NOT NULL,
    destinatario    VARCHAR(255)    NOT NULL,
    fecha_envio     DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    resultado       ENUM('Enviado','Fallido') NOT NULL,
    PRIMARY KEY (id),
    KEY idx_notif_alerta (alerta_id),
    KEY idx_notif_intervencion (intervencion_id),
    KEY idx_notif_resultado (resultado),
    CONSTRAINT fk_notif_alerta
        FOREIGN KEY (alerta_id) REFERENCES alerta (id)
        ON DELETE SET NULL ON UPDATE RESTRICT,
    CONSTRAINT fk_notif_intervencion
        FOREIGN KEY (intervencion_id) REFERENCES intervencion (id)
        ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Notificaciones emitidas por alerta o intervencion. FKs opcionales SET NULL.';


-- =============================================================================
-- 22. intervencion_activo
-- =============================================================================
CREATE TABLE intervencion_activo (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    intervencion_id      BIGINT UNSIGNED NOT NULL,
    activo_id            BIGINT UNSIGNED NOT NULL,
    estado_final_activo  VARCHAR(100)    NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_interv_activo (intervencion_id, activo_id),
    KEY idx_interv_activo_activo (activo_id),
    CONSTRAINT fk_interv_activo_interv
        FOREIGN KEY (intervencion_id) REFERENCES intervencion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_interv_activo_activo
        FOREIGN KEY (activo_id) REFERENCES activo (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Relacion N:M entre intervenciones y activos afectados.';


-- =============================================================================
-- 23. decision_intervencion
-- =============================================================================
CREATE TABLE decision_intervencion (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    intervencion_id BIGINT UNSIGNED NOT NULL,
    decisor_id      BIGINT UNSIGNED NOT NULL,
    decision        ENUM('Aprobada','Rechazada','CambiosSolicitados','ExcepcionVentana') NOT NULL,
    observacion     TEXT            NULL,
    fecha_hora      DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_decision_interv (intervencion_id),
    KEY idx_decision_decisor (decisor_id),
    CONSTRAINT fk_decision_interv
        FOREIGN KEY (intervencion_id) REFERENCES intervencion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_decision_decisor
        FOREIGN KEY (decisor_id) REFERENCES usuario (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Decisiones (aprobacion/rechazo) del flujo de una intervencion.';


-- =============================================================================
-- 24. reserva_recurso
-- =============================================================================
CREATE TABLE reserva_recurso (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    intervencion_id BIGINT UNSIGNED NOT NULL,
    activo_id       BIGINT UNSIGNED NULL,
    ubicacion_id    BIGINT UNSIGNED NULL,
    fecha_inicio    DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    fecha_fin       DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_reserva_interv (intervencion_id),
    -- Indices para deteccion de solapamientos por activo/ubicacion y rango de fechas
    KEY idx_reserva_activo_rango (activo_id, fecha_inicio, fecha_fin),
    KEY idx_reserva_ubicacion_rango (ubicacion_id, fecha_inicio, fecha_fin),
    CONSTRAINT fk_reserva_interv
        FOREIGN KEY (intervencion_id) REFERENCES intervencion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_reserva_activo
        FOREIGN KEY (activo_id) REFERENCES activo (id)
        ON DELETE SET NULL ON UPDATE RESTRICT,
    CONSTRAINT fk_reserva_ubicacion
        FOREIGN KEY (ubicacion_id) REFERENCES ubicacion (id)
        ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Reservas de recurso (activo/ubicacion) para intervenciones. Indices para deteccion de solapamientos. Nota: la deteccion de solapamiento se resuelve en la capa de aplicacion o via CHECK/consultas; MySQL no soporta exclusion constraints por rango de forma nativa.';


-- =============================================================================
-- 25. entrada_bitacora
-- =============================================================================
CREATE TABLE entrada_bitacora (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    intervencion_id BIGINT UNSIGNED NOT NULL,
    autor_id        BIGINT UNSIGNED NOT NULL,
    contenido       TEXT            NOT NULL,
    fecha_hora      DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
    PRIMARY KEY (id),
    KEY idx_bitacora_interv (intervencion_id),
    KEY idx_bitacora_autor (autor_id),
    CONSTRAINT fk_bitacora_interv
        FOREIGN KEY (intervencion_id) REFERENCES intervencion (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_bitacora_autor
        FOREIGN KEY (autor_id) REFERENCES usuario (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Entradas de bitacora de una intervencion.';


-- =============================================================================
-- 26. bitacora_activo
-- =============================================================================
CREATE TABLE bitacora_activo (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    entrada_bitacora_id BIGINT UNSIGNED NOT NULL,
    activo_id           BIGINT UNSIGNED NOT NULL,
    accion              VARCHAR(255)    NOT NULL,
    PRIMARY KEY (id),
    KEY idx_bitacora_activo_entrada (entrada_bitacora_id),
    KEY idx_bitacora_activo_activo (activo_id),
    CONSTRAINT fk_bitacora_activo_entrada
        FOREIGN KEY (entrada_bitacora_id) REFERENCES entrada_bitacora (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_bitacora_activo_activo
        FOREIGN KEY (activo_id) REFERENCES activo (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Detalle de activos referenciados en una entrada de bitacora.';


SET FOREIGN_KEY_CHECKS = 1;
SET SQL_MODE = @OLD_SQL_MODE;

-- =============================================================================
-- FIN DEL ESQUEMA BASE
-- =============================================================================


-- #############################################################################
-- #  BLOQUE OPCIONAL Y COMENTADO — PARTICIONAMIENTO SUGERIDO PARA `medicion`  #
-- #############################################################################
--
-- Justificacion: hasta 43.200 registros/sensor/dia (1 lectura cada 2 s).
-- Con multiples sensores el volumen crece rapido; el particionamiento por RANGE
-- mensual sobre fecha_hora_medicion facilita el "pruning" en consultas por rango
-- de fechas y el archivado/borrado por particiones (DROP PARTITION).
--
-- >>> VALIDAR EN STAGING ANTES DE PRODUCCION <<<
--
-- RESTRICCIONES IMPORTANTES DE MySQL/InnoDB PARA TABLAS PARTICIONADAS:
--   1) Las tablas particionadas NO admiten claves foraneas (ni salientes ni
--      entrantes). Por tanto, la version particionada de `medicion` NO puede
--      declarar el FK a `sensor`. La integridad sensor_id -> sensor debe
--      garantizarse en la capa de aplicacion.
--   2) La columna de particion DEBE formar parte de TODAS las claves unicas
--      (incluida la PK). Por eso la PK pasa a ser (id, fecha_hora_medicion) y la
--      UNIQUE de idempotencia pasa a (sensor_id, evento_id, fecha_hora_medicion).
--      NOTA: al incluir fecha_hora_medicion en la UNIQUE, la idempotencia estricta
--      por (sensor_id, evento_id) ya no la garantiza el motor si llegara el mismo
--      evento con distinta fecha; se recomienda reforzar la idempotencia en la
--      capa de ingesta (upsert por evento_id).
--   3) Mantener/crear particiones futuras de forma programada (job mensual) o
--      usar una particion MAXVALUE de contencion.
--
-- Ejemplo (crear la tabla YA particionada, reemplazando la definicion base):
--
-- CREATE TABLE medicion (
--     id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
--     sensor_id            BIGINT UNSIGNED NOT NULL,
--     evento_id            CHAR(36)        NOT NULL,
--     temperatura          DECIMAL(5,2)    NULL,
--     humedad              DECIMAL(5,2)    NULL,
--     fecha_hora_medicion  DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
--     fecha_hora_recepcion DATETIME        NOT NULL COMMENT 'UTC (RNF-INT-02)',
--     origen               ENUM('Real','Simulado') NOT NULL DEFAULT 'Real',
--     PRIMARY KEY (id, fecha_hora_medicion),
--     UNIQUE KEY uq_medicion_sensor_evento (sensor_id, evento_id, fecha_hora_medicion),
--     KEY idx_medicion_sensor_fecha (sensor_id, fecha_hora_medicion),
--     KEY idx_medicion_fecha (fecha_hora_medicion)
--     -- SIN FK a sensor (no permitido en tablas particionadas)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
--   COMMENT='SOLO INSERCION (inmutable). Particionada por mes.'
-- PARTITION BY RANGE (TO_DAYS(fecha_hora_medicion)) (
--     PARTITION p2026_01 VALUES LESS THAN (TO_DAYS('2026-02-01')),
--     PARTITION p2026_02 VALUES LESS THAN (TO_DAYS('2026-03-01')),
--     PARTITION p2026_03 VALUES LESS THAN (TO_DAYS('2026-04-01')),
--     PARTITION p2026_04 VALUES LESS THAN (TO_DAYS('2026-05-01')),
--     PARTITION p2026_05 VALUES LESS THAN (TO_DAYS('2026-06-01')),
--     PARTITION p2026_06 VALUES LESS THAN (TO_DAYS('2026-07-01')),
--     PARTITION p2026_07 VALUES LESS THAN (TO_DAYS('2026-08-01')),
--     PARTITION p2026_08 VALUES LESS THAN (TO_DAYS('2026-09-01')),
--     PARTITION p2026_09 VALUES LESS THAN (TO_DAYS('2026-10-01')),
--     PARTITION p2026_10 VALUES LESS THAN (TO_DAYS('2026-11-01')),
--     PARTITION p2026_11 VALUES LESS THAN (TO_DAYS('2026-12-01')),
--     PARTITION p2026_12 VALUES LESS THAN (TO_DAYS('2027-01-01')),
--     PARTITION p_max    VALUES LESS THAN MAXVALUE
-- );
--
-- Mantenimiento mensual sugerido (crear proxima particion antes de que llegue el mes):
--   ALTER TABLE medicion REORGANIZE PARTITION p_max INTO (
--     PARTITION p2027_01 VALUES LESS THAN (TO_DAYS('2027-02-01')),
--     PARTITION p_max    VALUES LESS THAN MAXVALUE
--   );
--
-- Archivado/purga eficiente por particion (en vez de DELETE masivo):
--   ALTER TABLE medicion DROP PARTITION p2026_01;
--
-- #############################################################################


-- #############################################################################
-- #  ALTERNATIVA OPCIONAL Y COMENTADA — NORMALIZAR destinatarios de reglas    #
-- #############################################################################
-- Si se prefiere normalizar `regla_alerta.destinatarios` (JSON) en tabla aparte:
--
-- CREATE TABLE regla_alerta_destinatario (
--     id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
--     regla_alerta_id BIGINT UNSIGNED NOT NULL,
--     destinatario   VARCHAR(255)    NOT NULL,
--     canal          ENUM('SMTP','PowerAutomate') NULL,
--     PRIMARY KEY (id),
--     KEY idx_rad_regla (regla_alerta_id),
--     CONSTRAINT fk_rad_regla
--         FOREIGN KEY (regla_alerta_id) REFERENCES regla_alerta (id)
--         ON DELETE CASCADE ON UPDATE RESTRICT
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- #############################################################################
