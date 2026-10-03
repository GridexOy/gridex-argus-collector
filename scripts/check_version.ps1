# check_version.ps1 - single gate wrapper (PowerShell 5.1); logic lives in scripts\gates\check_version.py.
& (Join-Path $PSScriptRoot 'run_gates.ps1') -Only version
exit $LASTEXITCODE
