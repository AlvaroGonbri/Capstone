# Respaldo de la evidencia de las pruebas de API de SICMA

La evidencia formal es el documento **SICMA - Evidencia de pruebas de API v1.0** (Word y PDF), que está en `Evidencias de documentación/Documentos de Gestión`. Es el adjunto del Anexo C de *Resultados de pruebas v2.1*.

Esta carpeta guarda el material de respaldo de ese documento:

| Carpeta | Contenido |
|---|---|
| `Capturas/Postman/` | Captura de pantalla de cada uno de los 158 casos ejecutados con la colección de Postman (Newman 6.2.1). La corrida fue el 21-11-2026. |
| `Capturas/Script/` | Captura de cada uno de los 16 casos que Postman no puede ejecutar. Cada captura dice por qué. |
| `Colección/` | La colección de Postman y su entorno, listos para importar. |

## Cómo leer una captura

- **Datos del caso.** Arriba están el resultado esperado del caso, la fecha y hora de ejecución, y la herramienta usada.
- **Solicitudes.** Cada solicitud muestra el método, la URL, las cabeceras, el cuerpo enviado y la respuesta real del servidor, con su cabecera `Date`.
- **Pruebas.** Las pruebas comprueban el resultado esperado. ✔ PASS significa que SICMA cumple; ✘ FAIL significa que no cumple. Los casos fallidos del informe se ven en rojo.
- **Datos ocultos.** La contraseña de prueba aparece como `{{clave}}` y los tokens de integración como `{{token_…}}`. Los JWT y las claves de dispositivo van acortados.
- **Pasos de colores (solo en las capturas de script).** En amarillo, cambios directos en la base de pruebas. En azul, consultas a la base. En morado, extractos del código revisado.

## Cómo repetir la corrida en Postman

1. Importa `Colección/SICMA-API.postman_collection.json` y `Colección/SICMA-pruebas.postman_environment.json`.
2. En el entorno, completa `clave` con la contraseña de las cuentas de prueba. Agrega también:
   - `zabbixSim`: dirección del simulador de Zabbix;
   - `correoSim`: dirección del servidor de correo de pruebas;
   - `token_webhook_zabbix` y `token_flujo`: los tokens del entorno de pruebas.
3. Ejecuta la colección completa y en orden con el *Collection Runner*.

**Ejecútala solo contra un entorno de pruebas recién creado.** La colección crea y modifica datos, bloquea cuentas y desactiva al Administrador Privilegiado (CP-REG-17). Nunca la ejecutes contra producción.
