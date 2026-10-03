# check_legacy.ps1 - single gate wrapper (PowerShell 5.1); logic lives in scripts\gates\check_legacy.py.
& (Join-Path $PSScriptRoot 'run_gates.ps1') -Only legacy
exit $LASTEXITCODE
