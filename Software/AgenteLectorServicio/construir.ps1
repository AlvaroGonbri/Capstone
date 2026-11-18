<#
  Construye el servicio "SICMA Lector" en .\dist (no necesita permisos de administrador):
    dist\agente_lector\agente_lector.exe   el agente empaquetado con PyInstaller (incluye Python)
    dist\SICMALector.exe + .xml            WinSW: lo registra y lo controla como servicio de Windows

  Uso:  .\construir.ps1
  Luego, como administrador:  .\instalar.ps1
#>
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$WinSWVersion = 'v2.12.0'
$WinSWUrl = "https://github.com/winsw/winsw/releases/download/$WinSWVersion/WinSW-x64.exe"

# Entorno aislado para la construcción: no instala nada en el Python del sistema
if (-not (Test-Path .\.venv-build\Scripts\python.exe)) {
    Write-Host 'Creando entorno de construcción (.venv-build)...'
    python -m venv .venv-build
}
$py = '.\.venv-build\Scripts\python.exe'
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet 'pyinstaller>=6.16,<7'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar PyInstaller.' }

Write-Host 'Empaquetando el agente con PyInstaller...'
& $py -m PyInstaller --noconfirm --clean --log-level WARN `
    --name agente_lector --console `
    --distpath dist --workpath build --specpath build `
    agente_lector.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller falló.' }

# WinSW: se descarga una vez y se guarda con el nombre del servicio
$winsw = 'dist\SICMALector.exe'
if (-not (Test-Path $winsw)) {
    Write-Host "Descargando WinSW $WinSWVersion..."
    Invoke-WebRequest -Uri $WinSWUrl -OutFile $winsw -UseBasicParsing
}
Copy-Item servicio\SICMALector.xml dist\SICMALector.xml -Force

$hash = (Get-FileHash $winsw -Algorithm SHA256).Hash
Write-Host ''
Write-Host 'Listo. Contenido de dist:'
Write-Host '  agente_lector\agente_lector.exe'
Write-Host "  SICMALector.exe (WinSW $WinSWVersion, SHA256 $hash)"
Write-Host '  SICMALector.xml'
Write-Host ''
Write-Host 'Siguiente paso, en PowerShell como administrador:  .\instalar.ps1'
