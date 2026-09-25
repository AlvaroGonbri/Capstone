# SICMA · Frontend

Plataforma web y movil del Sistema Integrado de Control y Monitoreo de Activos.
Una sola base de codigo Angular + Ionic: la version web y el APK salen del mismo proyecto.

## Requisitos

- Node.js 20 o superior
- npm 10 o superior

## Puesta en marcha

```bash
npm install
npm start          # servidor de desarrollo en http://localhost:4200
```

Usuarios de prueba mientras el API no exista:

| Correo              | Clave     | Rol           |
| ------------------- | --------- | ------------- |
| admin@sicma.cl      | sicma2026 | Administrador |
| tecnico@sicma.cl    | sicma2026 | Tecnico       |
| jefatura@sicma.cl   | sicma2026 | Jefatura      |

## Estructura

```
src/app/
  core/
    models/          Interfaces de dominio: activos, lecturas, accesos, intervenciones
    services/        Un servicio por modulo, mas el de autenticacion
    mock/            Datos de demostracion mientras no hay backend
    guards/          Proteccion de rutas
    interceptors/    Envio del token en cada llamada
  pages/
    login/           Ingreso
    panel/           Resumen general
    activos/         Listado y ficha de activo
    monitoreo/       Temperatura y humedad por sala
    accesos/         Registro de entradas y salidas
    intervenciones/  Bitacora de mantenciones
  shared/            Encabezado comun y pipes
```

## Conexion con el API Django

Todos los servicios ya hacen la llamada HTTP real. El cambio esta en un solo lugar:

```ts
// src/environments/environment.ts
usarDatosSimulados: false,
apiUrl: 'http://localhost:8000/api',
```

Rutas que el backend debe exponer:

| Modulo         | Ruta                     | Metodo |
| -------------- | ------------------------ | ------ |
| Autenticacion  | `/auth/login/`           | POST   |
| Activos        | `/activos/`              | GET    |
| Monitoreo      | `/monitoreo/sensores/`   | GET    |
| Monitoreo      | `/monitoreo/umbrales/`   | GET    |
| Accesos        | `/accesos/`              | GET    |
| Intervenciones | `/intervenciones/`       | GET    |

La forma exacta de cada respuesta esta en `src/app/core/models/index.ts`.

## Compilar

```bash
npm run build                  # salida en dist/sicma-frontend/browser
```

## Generar el APK

```bash
npm install @capacitor/android
npx cap add android
npm run build
npx cap sync
npx cap open android           # abre Android Studio para generar el APK
```

## Pendiente

- Formularios de alta y edicion de activos e intervenciones.
- Grafico historico de temperatura con rango de fechas.
- Manejo de roles en la interfaz: la jefatura no deberia ver las acciones de edicion.
