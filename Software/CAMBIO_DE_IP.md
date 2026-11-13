# Cambio de IP del PC del backend

Qué revisar cuando el PC donde corre el backend de SICMA cambia de IP en la red local
(por ejemplo, de `192.168.100.102` a otra).

## Antes de empezar

- **El PC del backend va por cable.** Usa el adaptador Ethernet USB, unido al switch de Hyper-V
  `ExternalSwitch`. El router no deja que los equipos WiFi (ESP32, celulares) inicien conexiones
  hacia un PC conectado por WiFi, así que con el PC en WiFi el Arduino no llega.
- **Para ver la IP actual**, ejecuta `ipconfig` y busca el adaptador **vEthernet (ExternalSwitch)**.
- **Lo ideal es no tener que usar este instructivo:** reserva la IP en el router (DHCP → reserva
  de IP) para la MAC `70-B5-E8-C4-0D-2E`, que es la del adaptador USB y la del ExternalSwitch.

## Qué cambiar

En los pasos siguientes, `NUEVA_IP` es la nueva dirección del PC.

### 1. Backend: `Software/Backend/.env`

Agrega la nueva IP al final de `ALLOWED_HOSTS`. Puedes dejar las antiguas.

```
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.100.102,api.sicma.cl,IP_TAILSCALE,NUEVA_IP
```

Si no lo haces, Django responde **400 Bad Request** a todo lo que llegue por la red local
(Arduino, otros equipos).

Después **reinicia la API**: cierra la ventana *SICMA · API (waitress)* y vuelve a ejecutar
`iniciar_sicma.ps1`. Waitress no toma cambios del `.env` mientras está corriendo.

### 2. Arduino (ESP32): el sketch `test_dht22.ino`

Cambia la URL y vuelve a subir el sketch:

```cpp
const char* API_URL = "http://NUEVA_IP:8000/api/mediciones/";
```

Verificación: en el Monitor Serie (115200 baudios) debe aparecer `[HTTP] 201 Registrada ...`,
y en SICMA → Arduinos el sensor debe pasar a **En línea**.

Para leer los errores del Monitor Serie:

| Mensaje | Causa |
|---|---|
| `Fallo (-1): connection refused` | El ESP32 no llega al PC: la API está apagada, la IP es incorrecta o el PC está en WiFi. |
| `400` | Falta la IP en `ALLOWED_HOSTS` o no se reinició la API. |
| `401/403` | La clave del dispositivo es incorrecta o el sensor está inactivo. No tiene que ver con la IP. |

### 3. Zabbix: media type *SICMA webhook*

En Zabbix, entra a **Alerts → Media types → SICMA webhook** y revisa la URL a la que envía los
eventos. Si apunta a la IP antigua (`http://192.168.100.102:8000/...`), cámbiala por `NUEVA_IP`.

Si no lo haces, SICMA sigue sincronizando los problemas cada 60 s con `sincronizar_zabbix`, pero
los avisos inmediatos del webhook no llegan.

### 4. Solo si usas la web de desarrollo desde otro equipo

`npm start` en el mismo PC usa `localhost` y no necesita cambios. Si abres la web de desarrollo
desde otro equipo de la red, agrega en `Software/Backend/backendsicma/settings.py`, dentro de
`CORS_ALLOWED_ORIGINS`:

```python
'http://NUEVA_IP:4200',
```

## Qué NO hay que cambiar

| Componente | Por qué no depende de la IP del PC |
|---|---|
| Web publicada (`app.sicma.cl`) y app móvil | Usan `https://api.sicma.cl`. |
| Túnel de Cloudflare (`config.yml`) | Apunta a `http://localhost:8000`. |
| Agente del lector en este PC (`agente_lector.ini`) | Usa `http://127.0.0.1:8000/api`. |
| PC cliente por Tailscale | Usa la IP de Tailscale del PC del backend (`IP_TAILSCALE`; se ve con `tailscale ip -4`), que no cambia. |
| MySQL (cuenta `sicma_app`) | Se conecta a través de MySQL Router (`router01`), no según la IP del PC. |
| Power Automate | El puente es por correo, no por IP. |
| Firewall de Windows | Está desactivado en redes privadas y públicas. Si algún día lo activas, permite la entrada al puerto 8000 (o a `python.exe`). |

## Si cambia la IP de otro equipo

| Equipo | IP actual | Dónde cambiarla |
|---|---|---|
| MySQL Router (`router01`) | 192.168.100.95 | `DB_HOST` en `Software/Backend/.env` y reiniciar los procesos. |
| Zabbix (`srv-vm-zabbix`) | 192.168.100.121 | `ZABBIX_URL` en `Software/Backend/.env`, y `Server=`/`ServerActive=` en el agente Zabbix de cada nodo (`/etc/zabbix/zabbix_agent2.conf`). |
| Nodos MySQL (`mysql01-03`) | .97 / .94 / .96 | La interfaz del host en Zabbix y la configuración del clúster (InnoDB Cluster / MySQL Router). |
| ESP32 | (por DHCP) | Nada: es el ESP32 el que se conecta al backend, no al revés. |

## Prueba final

1. **Desde el celular conectado al WiFi** (con los datos móviles apagados), abre
   `http://NUEVA_IP:8000/api/auth/users/`. Debe
   responder `{"detail":"Las credenciales de autenticación no se proveyeron."}`. Si no carga, el
   problema es de red: revisa la IP, el cable y que la API esté corriendo.
2. **En el Monitor Serie del ESP32**, debe aparecer `[HTTP] 201 Registrada`.
3. **En SICMA → Arduinos**, el sensor debe aparecer **En línea**.
