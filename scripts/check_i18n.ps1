# check_i18n.ps1 - single gate wrapper (PowerShell 5.1); logic lives in scripts\gates\check_i18n.py.
& (Join-Path $PSScriptRoot 'run_gates.ps1') -Only i18n
exit $LASTEXITCODE
