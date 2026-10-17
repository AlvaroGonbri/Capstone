# Contexto: integración Zabbix ↔ SICMA

Resumen del trabajo previo para continuar en Claude Code. Idioma de trabajo: español.

## Proyecto
SICMA (Sistema Integrado de Control y Monitoreo de Activos), proyecto APT/Capstone Duoc UC.
Backend Django + DRF (JWT con simplejwt), frontend Angular (web) e Ionic + Angular (móvil, solo lectura).

## Laboratorio (VMs Hyper-V en una sola máquina física, red 192.168.100.0/24, gateway .1)
| Host | IP | Rol |
|---|---|---|
| srv-vm-zabbix | 192.168.100.121 | Zabbix 7.0.31 LTS (server + frontend Apache/PHP-FPM 8.5 + MySQL local), Ubuntu 26.04 |
| mysql01 | 192.168.100.97 | Nodo InnoDB Cluster `miCluster` (MySQL 8.4.11) |
| mysql02 | 192.168.100.94 | Nodo InnoDB Cluster |
| mysql03 | 192.168.100.96 | Nodo InnoDB Cluster |
| router01 | 192.168.100.95 | MySQL Router (6446 R/W, 6447 R/O); el backend se conecta aquí |
| Host Hyper-V (Windows) | por confirmar | Zabbix Agent 2 7.0.31 para Windows |

- Cluster en modo Single-Primary. El primario puede cambiar (se movió a mysql01 durante una actualización).
- Todos los nodos tienen Zabbix Agent 2 con `Server=`/`ServerActive=192.168.100.121` y `Hostname=` igual al hostname.

## Configuración en Zabbix
- Grupos de hosts: `Cluster` (mysql01-03, router01) e `Hypervisores` (host Hyper-V).
- Plantillas: `Linux by Zabbix agent` (nodos y router), `MySQL by Zabbix agent 2` (nodos, usuario `zbx_monitor`), `Windows by Zabbix agent` (Hyper-V; ya descubre el servicio `vmms`).
- router01: items `proc.num[mysqlrouter]`, `net.tcp.listen[6446]`, `net.tcp.listen[6447]` con triggers `=0`.
- Group Replication: UserParameters `mysql.gr.online` y `mysql.gr.primary` (1/0 por nodo) en `/etc/zabbix/zabbix_agent2.d/group_replication.conf`, plantilla `MySQL Group Replication` y dashboard `Cluster MySQL` (Honeycomb).
- Usuario de API: `sicma_api`, grupo `SICMA` (Read sobre `Cluster` e `Hypervisores`), con API token.

## API de Zabbix
- URL: `http://192.168.100.121/zabbix/api_jsonrpc.php` (verificado: `apiinfo.version` → 7.0.31).
- JSON-RPC 2.0, solo POST, `Content-Type: application/json-rpc`. Un GET devuelve HTTP 412 (normal).
- Autenticación: `Authorization: Bearer <token>`. No usar `user.login` ni el campo `auth`.
- Los errores llegan con HTTP 200 y clave `error`. Todos los valores numéricos vienen como strings.
- Solo métodos `.get` (usuario de solo lectura).

## Código ya escrito (copiar a la app Django)
- `zabbix_client.py`: clase `ZabbixClient` con `hosts()`, `problemas()`, `estado_cluster()` e `historial()`.
- `views_zabbix.py`: vistas DRF con caché de 30 s y respuesta 503 si Zabbix falla:
  - `GET /api/infraestructura/estado/` → cluster + problemas activos
  - `GET /api/infraestructura/hosts/` → hosts y disponibilidad del agente
  - `POST /api/integraciones/zabbix/webhook/` → valida `X-Zabbix-Token` con `hmac.compare_digest`
- Variables de entorno: `ZABBIX_URL`, `ZABBIX_TOKEN`, `ZABBIX_WEBHOOK_SECRET` (nunca en el código ni en el frontend).
- El frontend nunca llama a Zabbix directamente; solo consume los endpoints de SICMA con su JWT.

## Pendiente
1. Integrar los dos archivos en la app Django y registrar las rutas bajo el prefijo `api/` del proyecto.
2. Probar el token de `sicma_api` con `host.get` y luego los endpoints de SICMA.
3. Script del media type Webhook en Zabbix (POST al endpoint con `X-Zabbix-Token`) y la Action correspondiente.
4. Guardar los eventos del webhook en un modelo de SICMA (hay un TODO en `ZabbixWebhookView`).
5. Servicio Angular `InfraestructuraService` con interfaces TypeScript y refresco cada 30 s.
6. Tests con `requests` mockeado.
