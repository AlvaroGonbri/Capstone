# Cambio de tokens y secretos

Qué hacer para renovar cada token, clave o secreto de SICMA: dónde está, cómo se cambia, en qué
otro sistema hay que actualizarlo y qué procesos reiniciar.

La vista **Integraciones** de SICMA (menú Seguridad) muestra el estado de cada integración y permite
probarlas. Además, renueva desde ahí los dos secretos que genera SICMA. El resto se cambia a mano,
como se explica abajo.

## Antes de empezar

- **Nunca subas un secreto a GitHub** ni lo pegues en un documento o en un chat. El `.env` no se
  versiona; revisa `git status` antes de cada commit.
- **Para generar un secreto aleatorio:**

  ```
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- **Para reiniciar los procesos**, cierra las ventanas que abrió `iniciar_sicma.ps1` (API,
  sincronización de Zabbix, buzón de intervenciones y lector) y vuelve a ejecutarlo. Si cambiaste
  una variable de entorno de Windows, ejecútalo desde una ventana **nueva** de PowerShell: las que ya
  estaban abiertas conservan el valor antiguo.

## Resumen

| Secreto | Dónde está | Cómo se renueva | También se cambia en | Reiniciar |
|---|---|---|---|---|
| Secreto del webhook de Zabbix | Base de datos (hash), o `ZABBIX_WEBHOOK_SECRET` del `.env` si nunca se renovó | **Desde la vista Integraciones** | El *Media type* del webhook en Zabbix | Nada |
| Token del flujo de Power Automate | Base de datos (hash), o `INTERVENCIONES_TOKEN` del `.env` si nunca se renovó | **Desde la vista Integraciones** | El flujo de Power Automate | Nada |
| Claves de sensores ESP32 | Base de datos (hash) | **Desde la web:** Catálogos › Dispositivos IoT › Regenerar clave | El sketch del ESP32 (volver a cargarlo) | Nada |
| Claves de los lectores biométricos | Base de datos (hash) | **Desde la web:** Accesos › Lectores › Regenerar clave | `agente_lector.ini` del PC del lector | Agente del lector |
| Token de API de Zabbix | `.env` → `ZABBIX_TOKEN` | En Zabbix | — | API y sincronización de Zabbix |
| Clave de Gemini (resumen de Reportes) | `.env` → `GEMINI_API_KEY` | En Google AI Studio | — | API |
| Contraseña de Gmail | Variables de usuario de Windows `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | En la cuenta de Google | — | Todos |
| `SECRET_KEY` de Django | `.env` | Generar una nueva | — | API |
| Clave de MySQL (`sicma_app`) | `.env` → `DB_PASSWORD` | En MySQL | — | Todos |

## Secretos que se renuevan desde la vista Integraciones

Solo los puede renovar el **Administrador Privilegiado** y solo desde la red local. La ruta no se
publica por el túnel, así que desde sicma.brionessolutions.cl se ve el estado pero no se puede renovar.

1. En Integraciones, en la tarjeta del webhook o del buzón, usa **Renovar…**.
2. Escribe tu contraseña. Marca **«anularlo de inmediato»** solo si el valor actual pudo filtrarse.
   Si no lo marcas, el valor anterior sigue sirviendo 24 horas, para que alcances a reemplazarlo
   sin perder avisos.
3. Copia el valor nuevo. SICMA guarda solo su hash y **no lo vuelve a mostrar**.
4. Pégalo en el otro sistema:
   - **Webhook de Zabbix:** en Zabbix, *Alerts › Media types* › el webhook de SICMA. Reemplaza el
     parámetro que se envía en la cabecera `X-Zabbix-Token` y guarda. Prueba con el botón *Test*:
     SICMA no debe responder 403.
   - **Flujo de Power Automate:** edita el flujo de intervenciones y reemplaza el campo `"token"`
     del JSON en cada acción que envía un correo a SICMA (solicitud nueva y decisión). Guarda.
5. Desde ese momento SICMA usa el valor de la base de datos. La variable del `.env`
   (`ZABBIX_WEBHOOK_SECRET` o `INTERVENCIONES_TOKEN`) ya no se usa y puedes borrarla.

Cada renovación queda en el registro de la vista, con usuario, fecha e IP, y avisa por correo a
todos los Administradores Privilegiados. El valor del secreto nunca aparece en el registro ni en
el correo.

## Secretos que se cambian a mano

### Token de API de Zabbix

1. En Zabbix: *Users › API tokens › Create API token*, para el usuario `sicma_api`. Ponle fecha
   de vencimiento.
2. Reemplaza `ZABBIX_TOKEN` en `Software/Backend/.env`.
3. Reinicia la API y la sincronización de Zabbix.
4. En Integraciones, usa **Probar** en la tarjeta de Zabbix. Si funciona, elimina el token
   antiguo en Zabbix.

### Clave de Gemini (resumen de Reportes)

Es opcional: sin ella, Reportes arma el resumen con una plantilla y todo lo demás funciona igual.

1. En aistudio.google.com, *Get API key › Create API key*. La clave empieza con `AIza`.
2. Ponla en `GEMINI_API_KEY` de `Software/Backend/.env`. El modelo se cambia con `GEMINI_MODELO`;
   por defecto es `gemini-3.5-flash`. Google retira modelos con el tiempo: si Reportes o **Probar**
   dicen «Google ya no ofrece el modelo… (HTTP 404)», pon en `GEMINI_MODELO` uno vigente del listado
   de AI Studio (de preferencia un *Flash*) y reinicia la API.
3. Reinicia la API.
4. En Integraciones, usa **Probar** en la tarjeta de Gemini. Si la clave anterior pudo filtrarse,
   elimínala en AI Studio.

En el nivel gratuito, Google puede usar lo que recibe para mejorar sus productos. Por eso SICMA solo
le envía cifras agregadas del período: nunca nombres de personas, servidores, zonas ni IPs.

### Contraseña de aplicación de Gmail

1. En la cuenta de Google del buzón de SICMA: *Seguridad › Contraseñas de aplicación*, crea una
   nueva.
2. Reemplaza la variable de usuario de Windows `EMAIL_HOST_PASSWORD`. Para hacerlo, abre
   Configuración y busca «Editar las variables de entorno de esta cuenta». Ponerla en el `.env` no
   sirve: la variable de Windows tiene prioridad.
3. Cierra las ventanas de SICMA y ejecuta `iniciar_sicma.ps1` desde una ventana nueva de
   PowerShell.
4. En Integraciones, usa **Probar** en la tarjeta de Correo. SICMA inicia sesión para enviar y
   para leer, sin enviar ningún correo. Si funciona, revoca la contraseña antigua en Google.

### `SECRET_KEY` de Django

1. Genera una nueva:

   ```
   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
   ```

2. Reemplázala en el `.env`. Si contiene caracteres especiales, déjala entre comillas simples.
3. Reinicia la API.

Cambiarla **cierra todas las sesiones**: todos deben volver a ingresar. También invalida los
enlaces de recuperación de contraseña que estén pendientes.

### Clave de MySQL de `sicma_app`

1. Cámbiala primero en MySQL, conectado al nodo primario del clúster. El cambio se replica a los
   demás nodos.
2. Reemplaza `DB_PASSWORD` en el `.env`.
3. Reinicia todos los procesos.

Si el orden se invierte, SICMA queda sin acceso a la base hasta que ambos valores coincidan.

### Claves de sensores y lectores

- **Sensor ESP32:** en Catálogos › Dispositivos IoT, usa *Regenerar clave*, copia la clave y
  cárgala en el sketch del ESP32. La anterior deja de funcionar de inmediato.
- **Lector biométrico:** en Accesos › Lectores, usa *Regenerar clave*, cópiala en
  `agente_lector.ini` del PC del lector y reinicia el agente.

### Túnel de Cloudflare

Las credenciales del túnel están en la carpeta `.cloudflared` del usuario de Windows y se
administran desde Cloudflare. No se renuevan desde SICMA. En Integraciones, **Probar** en la
tarjeta del túnel confirma que la API responde por su dirección pública y que las rutas internas
(webhook, lector y sensores) siguen bloqueadas desde internet. Si responde «el túnel no llega a
SICMA», revisa que el servicio de Windows `cloudflared` esté iniciado.
