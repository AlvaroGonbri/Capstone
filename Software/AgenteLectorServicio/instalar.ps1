<#
  Instala (o reinstala) el servicio de Windows "SICMA Lector". Ejecutar en PowerShell COMO ADMINISTRADOR,
  con la misma cuenta de Windows que usa el agente de consola actual (para poder copiar sus plantillas).

    .\instalar.ps1                                   toma punto_id, clave, URL y SDK del agente actual
    .\instalar.ps1 -Url http://192.168.100.52:8000/api   además cambia la URL de la API
    .\instalar.ps1 -SinMigrar                        no copia las plantillas del agente actual

  El agente actual (..\AgenteLector y C:\ProgramData\SICMA\lector) NO se modifica: sus plantillas solo
  se leen. Antes de instalar hay que cerrar su ventana: el lector no se puede abrir dos veces.

  Queda así:
    C:\Program Files\SICMA\Lector\               programa (agente, WinSW y SDK)
    C:\ProgramData\SICMA\LectorServicio\         configuración, plantillas, pendientes y logs
                                                 (solo SYSTEM y administradores)
#>
param(
    [string]$Url,
    [string]$ConfigOrigen = (Join-Path $PSScriptRoot '..\AgenteLector\agente_lector.ini'),
    [string]$PlantillasOrigen = (Join-Path $env:ProgramData 'SICMA\lector\plantillas.dat'),
    [switch]$SinMigrar
)
$ErrorActionPreference = 'Stop'

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Ejecuta este script en PowerShell como administrador.'
}

$dist = Join-Path $PSScriptRoot 'dist'
$programa = Join-Path $env:ProgramFiles 'SICMA\Lector'
$datos = Join-Path $env:ProgramData 'SICMA\LectorServicio'
$ini = Join-Path $datos 'agente_lector.ini'
$plantillas = Join-Path $datos 'plantillas.dat'
$winsw = Join-Path $programa 'SICMALector.exe'

foreach ($f in 'agente_lector\agente_lector.exe', 'SICMALector.exe', 'SICMALector.xml') {
    if (-not (Test-Path (Join-Path $dist $f))) { throw "Falta dist\$f. Ejecuta primero .\construir.ps1" }
}

# El lector no se puede abrir dos veces: el agente de consola tiene que estar cerrado
$consola = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -match 'agente_lector\.py.*escuchar' }
if ($consola) {
    throw "El agente de consola está corriendo (PID $($consola.ProcessId -join ', ')). Cierra su ventana " +
          '(SICMA · Lector biométrico) y vuelve a ejecutar este script.'
}

function Leer-Ini([string]$ruta) {
    $valores = @{}
    foreach ($linea in Get-Content -LiteralPath $ruta -Encoding UTF8) {
        if ($linea -match '^\s*([A-Za-z_]+)\s*=\s*(.*?)\s*$') { $valores[$Matches[1]] = $Matches[2] }
    }
    return $valores
}

# 1. Si ya estaba instalado, se detiene y se quita el registro anterior (los datos se conservan)
if (Get-Service -Name SICMALector -ErrorAction SilentlyContinue) {
    Write-Host 'Deteniendo y quitando la instalación anterior del servicio...'
    & $winsw stop | Out-Null
    & $winsw uninstall | Out-Null
    Start-Sleep -Seconds 2
}

# 2. Programa
Write-Host "Copiando el programa a $programa..."
New-Item -ItemType Directory -Force -Path $programa | Out-Null
if (Test-Path "$programa\agente") { Remove-Item -Recurse -Force "$programa\agente" }
Copy-Item -Recurse "$dist\agente_lector" "$programa\agente"
Copy-Item "$dist\SICMALector.exe", "$dist\SICMALector.xml" $programa -Force

# 3. Datos: carpeta solo para SYSTEM (S-1-5-18) y Administradores (S-1-5-32-544).
#    Se usan los SID porque los nombres de grupo cambian según el idioma de Windows.
New-Item -ItemType Directory -Force -Path $datos, "$datos\logs" | Out-Null
icacls $datos /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T /Q | Out-Null
if ($LASTEXITCODE -ne 0) { throw "No se pudieron fijar los permisos de $datos." }

# 4. Configuración: se crea a partir de la del agente de consola (la clave no se muestra)
if (-not (Test-Path $ini)) {
    if (-not (Test-Path $ConfigOrigen)) {
        throw "No está $ConfigOrigen. Indica otra con -ConfigOrigen, o crea $ini a partir de agente_lector.ini.example."
    }
    $origen = Leer-Ini $ConfigOrigen
    if (-not $origen['punto_id'] -or -not $origen['clave']) { throw "$ConfigOrigen no tiene punto_id y clave." }
    $urlFinal = if ($Url) { $Url } elseif ($origen['url']) { $origen['url'] } else { 'http://127.0.0.1:8000/api' }
    $contenido = @"
# Servicio "SICMA Lector". Creado por instalar.ps1 a partir de $ConfigOrigen.
# Tras modificarlo:  Restart-Service SICMALector

[sicma]
url = $urlFinal
punto_id = $($origen['punto_id'])
clave = $($origen['clave'])

[secugen]
dir_sdk = $programa\sdk
"@
    [IO.File]::WriteAllText($ini, $contenido, (New-Object Text.UTF8Encoding $false))
    Write-Host "Configuración creada en $ini (API: $urlFinal)."
    $dirSdkOrigen = $origen['dir_sdk']
} else {
    Write-Host "Se mantiene la configuración existente: $ini"
    if ($Url) {
        $texto = [IO.File]::ReadAllText($ini) -replace '(?m)^url\s*=.*$', "url = $Url"
        [IO.File]::WriteAllText($ini, $texto, (New-Object Text.UTF8Encoding $false))
        Write-Host "URL de la API cambiada a $Url."
    }
    $dirSdkOrigen = if (Test-Path $ConfigOrigen) { (Leer-Ini $ConfigOrigen)['dir_sdk'] } else { $null }
}

# 5. SDK de SecuGen: sus DLL se copian junto al programa (no dependen de una carpeta de usuario)
if (-not (Test-Path "$programa\sdk\sgfplib.dll")) {
    if (-not $dirSdkOrigen -or -not (Test-Path (Join-Path $dirSdkOrigen 'sgfplib.dll'))) {
        throw "No se encontró sgfplib.dll en '$dirSdkOrigen'. Revisa dir_sdk en $ConfigOrigen."
    }
    New-Item -ItemType Directory -Force -Path "$programa\sdk" | Out-Null
    Copy-Item (Join-Path $dirSdkOrigen '*') "$programa\sdk" -Recurse -Force
    Write-Host 'SDK de SecuGen copiado.'
}

# 6. Plantillas: se leen las del agente de consola y se guardan cifradas con la clave del equipo
$agente = "$programa\agente\agente_lector.exe"
if (-not $SinMigrar -and -not (Test-Path $plantillas)) {
    if (Test-Path $PlantillasOrigen) {
        Write-Host 'Copiando las plantillas del agente de consola (el original no se modifica)...'
        & $agente --config $ini migrar --origen $PlantillasOrigen
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron copiar las plantillas.' }
    } else {
        Write-Host "No hay plantillas en $PlantillasOrigen; el servicio parte sin huellas enroladas."
    }
}

# 7. Servicio
Write-Host 'Registrando e iniciando el servicio SICMALector...'
& $winsw install
if ($LASTEXITCODE -ne 0) { throw 'WinSW no pudo registrar el servicio.' }
& $winsw start
Start-Sleep -Seconds 4
Get-Service SICMALector | Format-Table Status, Name, DisplayName, StartType -AutoSize

$log = Join-Path $datos 'logs\SICMALector.out.log'
Write-Host 'Últimas líneas del registro:'
if (Test-Path $log) { Get-Content $log -Tail 10 } else { Write-Host '  (todavía vacío)' }
Write-Host ''
Write-Host "Seguir el registro:  Get-Content '$log' -Tail 20 -Wait"
Write-Host "Errores de arranque: $(Join-Path $datos 'logs\SICMALector.err.log')"
