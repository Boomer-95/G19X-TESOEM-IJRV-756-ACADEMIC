# Ejecutar desde la raiz: .\scripts\deploy_demo.ps1
#Requires -Version 5.1
. (Join-Path $PSScriptRoot 'demo_windows.ps1')
Invoke-DemoWindows -Accion deploy
