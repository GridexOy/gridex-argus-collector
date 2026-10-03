# check_size.ps1 - single gate wrapper (PowerShell 5.1); logic lives in scripts\gates\check_size.py.
& (Join-Path $PSScriptRoot 'run_gates.ps1') -Only size
exit $LASTEXITCODE
