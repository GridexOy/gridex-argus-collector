# check_docs.ps1 - single gate wrapper (PowerShell 5.1); logic lives in scripts\gates\check_docs.py.
& (Join-Path $PSScriptRoot 'run_gates.ps1') -Only docs
exit $LASTEXITCODE
