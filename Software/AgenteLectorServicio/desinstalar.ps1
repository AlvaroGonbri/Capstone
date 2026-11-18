<#
  Quita el servicio "SICMA Lector". Ejecutar en PowerShell COMO ADMINISTRADOR.

    .\desinstalar.ps1                  quita el servicio y el programa; conserva configuración y plantillas
    .\desinstalar.ps1 -BorrarDatos     además borra C:\ProgramData\SICMA\LectorServicio
                                       (plantillas del servicio, pendientes y logs; no se puede deshacer)

  No toca el agente de consola (..\AgenteLector ni C:\ProgramData\SICMA\lector).
#>
param([switch]$BorrarDatos)
$ErrorActionPreference = 'Stop'

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Ejecuta este script en PowerShell como administrador.'
}

$programa = Join-Path $env:ProgramFiles 'SICMA\Lector'
$datos = Join-Path $env:ProgramData 'SICMA\LectorServicio'
$winsw = Join-Path $programa 'SICMALector.exe'

if (Get-Service -Name SICMALector -ErrorAction SilentlyContinue) {
    Write-Host 'Deteniendo y quitando el servicio...'
    & $winsw stop | Out-Null
    & $winsw uninstall | Out-Null
    Start-Sleep -Seconds 2
} else {
    Write-Host 'El servicio no estaba instalado.'
}

if (Test-Path $programa) {
    Remove-Item -Recurse -Force $programa
    Write-Host "Programa eliminado: $programa"
}

if ($BorrarDatos) {
    if (Test-Path $datos) {
        Remove-Item -Recurse -Force $datos
        Write-Host "Datos eliminados: $datos"
    }
} else {
    Write-Host "Se conservan configuración y plantillas en $datos (usa -BorrarDatos para eliminarlas)."
}
