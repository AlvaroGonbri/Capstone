# Rediseño visual de SICMA · frontend

Cambio **solo visual** sobre `Software/sicma-frontend` del repositorio `AlvaroGonbri/Capstone`
(commit base `4780d6b`, 26/10/2026). Aplica la estética del documento
*SICMA_Mockup_Rediseno.pdf* a todas las vistas de la web y de la app móvil.

## Cómo aplicarlo

1. Reemplazar la carpeta `Software/sicma-frontend` del repositorio por la de este zip
   (o copiar encima los archivos de la lista de más abajo).
2. Ejecutar `npm install` (se agregaron dos paquetes de tipografías, ver abajo).
3. Probar como siempre:
   - Web: `npm start` (desarrollo) o `npm run build` (producción, Cloudflare Pages).
   - Móvil: `npm run movil` (compila la configuración `movil` y sincroniza Android).

Las tres configuraciones (`development`, `production` y `movil`) compilan sin errores ni advertencias.

## Lo que NO cambió

- **Entornos:** `environment.ts`, `environment.prod.ts` y `environment.movil.ts` quedan idénticos
  (URLs `192.168.100.102:8000`, `api.sicma.cl`, `soloConsulta`, tiempos de refresco, datos simulados en `false`).
- **Servicios y modelos** de `src/app/core` (llamadas al API, endpoints, mapeos, datos simulados).
- **Seguridad:** interceptor JWT con renovación de token, guards por rol, cierre por inactividad.
- **Rutas** (`app.routes.ts`), `app.config.ts`, `angular.json`, `capacitor.config.ts` y la carpeta `android`.
- **Comportamiento de cada pantalla:** mismos campos, validaciones, botones, permisos y flujos.
  Solo cambia cómo se ven y cómo se ordenan.
- **Estado de los sensores:** se muestra tal como lo entrega el backend. La regla "Sin datos"
  (desconectado tras X minutos sin lecturas) que aparece en el mockup **no** se implementó, por decisión del equipo.

## Cambios generales

| Archivo | Qué cambia |
|---|---|
| `package.json` / `package-lock.json` | Se agregan `@fontsource/inter` y `@fontsource/jetbrains-mono` (tipografías locales; funcionan sin internet en la app móvil). |
| `src/styles.scss` | Nuevo tema: paleta (consola, teal SICMA, estados), tipografías, tarjetas con borde fino, chips de estado suaves, pestañas tipo píldora, campos con borde, botones. Las clases utilitarias existentes se conservan (`contenido-limitado`, `rejilla-tarjetas`, `dato-grande`, `vacio`, etc.) y se agregan `titulo-seccion`, `aviso` y `grilla-datos`. |
| `src/app/app.html`, `app.ts`, `app.scss` | Menú lateral oscuro agrupado en **Operación / Inventario / Seguridad**, con usuario y "Cerrar sesión" abajo. La visibilidad por rol es la misma de antes (Usuarios solo para administradores; Técnico sin Accesos; Contratistas solo Personal externo). En la **app móvil** (`soloConsulta: true`) el menú se reemplaza por **pestañas inferiores**: Panel, Activos, Ambiente, Trabajos y Salir. |
| `src/app/shared/encabezado.component.ts` | Barra superior blanca con la sección encima del título (nuevo input opcional `seccion`). |
| `src/app/shared/pantalla-ingreso.component.ts` (nuevo) | Marco de las pantallas sin sesión: panel de marca a la izquierda y tarjeta del formulario a la derecha (en teléfono, solo la tarjeta). |

**Modo oscuro:** se quitó la paleta oscura automática (`dark.system.css`) porque esta identidad está pensada
para fondo claro. Se reactiva agregando de nuevo ese import en `styles.scss`.

## Cambios por vista

| Vista | Archivos | Qué cambia |
|---|---|---|
| Ingreso, Recuperar, Nueva contraseña, Cambiar contraseña | `login/*`, `recuperar/*`, `recuperar-confirmar/*`, `cambiar-clave/*` | Usan el nuevo marco de ingreso. Mensajes de error y éxito dentro de la tarjeta. El campo de contraseña muestra el botón de ver dentro del mismo borde. |
| Panel | `panel/*` | KPI con ícono y franja de color según el estado; 2 × 2 en teléfono. Alertas ambientales y trabajos abiertos en dos columnas, con chips de estado de color (`colorEstadoIntervencion`, que ya existía). |
| Activos | `activos/activos.page.*` | Lista convertida en **tabla** en escritorio (Activo, Tipo, Ubicación, Responsable, Criticidad, Zabbix, Estado) y tarjetas en teléfono. Las alertas de Zabbix pasan a una **franja resumida** con conteo por severidad; el detalle (con Reconocer y Cerrar) se despliega con un botón. |
| Ficha de activo | `activos/activo-detalle.page.*` | Cabecera con nombre y estado; datos en grilla (etiqueta arriba, valor abajo); Zabbix en grilla; historial de eventos como **línea de tiempo**; dos columnas en escritorio. |
| Nuevo / editar activo | `activos/activo-form.page.*` | Formulario en dos tarjetas (Identificación; Ubicación y responsabilidad) a dos columnas, botón de guardar al final a la derecha. |
| Monitoreo ambiental | `monitoreo/*` | Dos columnas: sensores a la izquierda; alertas abiertas y umbrales a la derecha. Cada lectura muestra una **barra con el rango permitido** y dónde cae el valor (solo presentación, con los mismos umbrales). Se mantiene la tendencia. |
| Arduinos | `arduinos/*` | Tarjeta por dispositivo con ícono, lecturas grandes, rangos y última lectura en grilla. |
| Intervenciones | `intervenciones/*` | En escritorio, **lista a la izquierda y detalle a la derecha** (en teléfono se despliega bajo la tarjeta, como antes). El detalle muestra el **avance del flujo** (Solicitada, Aprobada, En ejecución, Cerrada). Formularios y acciones sin cambios. |
| Accesos | `accesos/*` | Filtros dentro de una tarjeta; filas con borde de color por resultado (Permitido verde, Denegado rojo, Error ámbar); días del permiso como píldoras; en Lectores y Permisos, lista a la izquierda y formulario a la derecha. |
| Catálogos | `catalogos/*` | Formularios de alta en tarjeta, aviso de clave nueva destacado, chips de estado. |
| Personal externo | `personal/*` | Ficha y enrolamiento con el nuevo estilo de tarjetas y títulos. |
| Usuarios | `usuarios/*` | Política de contraseñas en una franja; lista de cuentas a la izquierda y formulario fijo a la derecha. |

## Funciones nuevas en TypeScript (todas de presentación)

- `app.ts`: `secciones` (menú agrupado), `pestanas` y `pestanasVisibles` (app móvil), `iniciales` (avatar).
- `activos.page.ts`: `alertasDesplegadas`, `alertasPorSeveridad`, `colorCriticidad`.
- `monitoreo.page.ts`: `barra()` calcula la posición del rango y la lectura en la barra.
- `intervenciones.page.ts`: `pasos` y `pasoActual()` para la línea de avance.

Ninguna hace llamadas nuevas al API ni modifica datos.

## Del mockup que quedó fuera (necesitaría datos o lógica nueva)

- Estado "Sin datos" de sensores y hora relativa ("hace 14 días").
- Gráfico de temperatura y humedad de 30 días y grilla de servidores Zabbix en el Panel
  (el Panel no consulta hoy el historial ni los hosts).
- Agrupar fallas repetidas del lector en Accesos y KPI de accesos.
- Color distinto por rol en Usuarios (hoy el chip indica si la cuenta está activa).
- Contadores en el menú lateral.
