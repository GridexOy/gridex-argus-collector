# check_no_cyrillic.ps1 - single gate wrapper (PowerShell 5.1); logic lives in scripts\gates\check_no_cyrillic.py.
& (Join-Path $PSScriptRoot 'run_gates.ps1') -Only no_cyrillic
exit $LASTEXITCODE
