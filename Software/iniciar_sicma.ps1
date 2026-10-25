# Abre los procesos de SICMA, cada uno en su propia ventana de PowerShell.
#   .\iniciar_sicma.ps1               los cuatro
#   .\iniciar_sicma.ps1 -SinLector    sin el agente del lector biométrico
# Para detener uno, Ctrl+C en su ventana (o cerrarla).
param([switch]$SinLector)

$raiz = $PSScriptRoot
$backend = Join-Path $raiz 'Backend'
$agente = Join-Path $raiz 'AgenteLector'

$procesos = @(
    # waitress: servidor apto para publicar (runserver es solo para desarrollo). No recarga al cambiar el
    # código: después de un cambio, cerrar su ventana y volver a ejecutar este script.
    @{ Titulo = 'SICMA · API (waitress)'; Carpeta = $backend; Comando = 'python -m waitress --listen=0.0.0.0:8000 --threads=8 backendsicma.wsgi:application' },
    @{ Titulo = 'SICMA · Zabbix'; Carpeta = $backend; Comando = 'python .\manage.py sincronizar_zabbix' },
    @{ Titulo = 'SICMA · Buzón de intervenciones'; Carpeta = $backend; Comando = 'python .\manage.py procesar_intervenciones' }
)
if (-not $SinLector) {
    $procesos += @{ Titulo = 'SICMA · Lector biométrico'; Carpeta = $agente; Comando = 'python .\agente_lector.py escuchar' }
}

foreach ($p in $procesos) {
    $script = "`$Host.UI.RawUI.WindowTitle = '$($p.Titulo)'; Set-Location '$($p.Carpeta)'; $($p.Comando)"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $script
    Write-Host "Iniciado: $($p.Titulo)"
}
