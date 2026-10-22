# Compartido: PowerShell 5.1/7. Python solo usa biblioteca estandar.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-DemoWindows {
    param([ValidateSet('restore', 'deploy')][string]$Accion)
    $ejecutor = Join-Path $PSScriptRoot 'demo_windows.py'
    foreach ($nombre in @('py', 'python3', 'python')) {
        $comando = Get-Command $nombre -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $comando) { continue }
        $prefijo = @()
        if ($nombre -eq 'py') { $prefijo = @('-3') }
        & $comando.Source @prefijo -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' *> $null
        if ($LASTEXITCODE -ne 0) { continue }
        & $comando.Source @prefijo $ejecutor $Accion
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        return
    }
    throw 'Se requiere Python 3.9 o posterior (py -3, python3 o python) y Docker Desktop con Compose v2.'
}
