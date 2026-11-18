# Agente del lector como servicio de Windows

Copia del agente de [../AgenteLector](../AgenteLector) que corre como el servicio **SICMA Lector**:
arranca con Windows sin que nadie inicie sesión, no muestra ventanas y se reinicia solo si falla.
El agente de consola no se modifica; los dos no pueden usar el lector al mismo tiempo.

| | Agente de consola | Servicio |
|---|---|---|
| Programa | `Software\AgenteLector` + Python instalado | `C:\Program Files\SICMA\Lector` (incluye Python) |
| Datos | `C:\ProgramData\SICMA\lector` | `C:\ProgramData\SICMA\LectorServicio` (solo SYSTEM y administradores) |
| Plantillas | Cifradas con la cuenta del usuario (DPAPI) | Cifradas con la clave del equipo (DPAPI) |
| Registros | En la ventana | `LectorServicio\logs`, 5 archivos de 1 MB |

## Instalar

1. `.\construir.ps1` (sin permisos de administrador). Genera `dist\`: el agente empaquetado con
   PyInstaller y WinSW, que lo registra como servicio.
2. Cerrar la ventana del agente de consola.
3. En PowerShell **como administrador**, con la misma cuenta que usa el agente de consola:
   `.\instalar.ps1 -Url http://<IP-del-backend>:8000/api`

   Toma `punto_id`, `clave` y el SDK de `..\AgenteLector\agente_lector.ini`, copia las plantillas
   (el original no se modifica: no hay que volver a enrolar) e inicia el servicio.

Si PowerShell no deja ejecutar scripts: `powershell -ExecutionPolicy Bypass -File .\instalar.ps1`.

## Operar

```powershell
Get-Service SICMALector                                    # estado
Restart-Service SICMALector                                # tras cambiar agente_lector.ini
Get-Content "$env:ProgramData\SICMA\LectorServicio\logs\SICMALector.out.log" -Tail 20 -Wait
```

Comandos de mantención (detén el servicio antes, el lector no se abre dos veces):

```powershell
& "$env:ProgramFiles\SICMA\Lector\agente\agente_lector.exe" prueba
& "$env:ProgramFiles\SICMA\Lector\agente\agente_lector.exe" listar
```

## Volver al agente de consola

`.\desinstalar.ps1` y abrir el agente de consola como antes. Sus datos no se tocaron, pero no tendrá
las huellas enroladas mientras corría el servicio.
