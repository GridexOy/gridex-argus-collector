# run_gates.ps1 - run every gate of TZ_SELAIN section 12.3 (PowerShell 5.1).
# Uses the repo venv when present, else the installed venv, else python on PATH.
param([string[]]$Only)
$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$candidates = @((Join-Path $repo '.venv\Scripts\python.exe'),
                (Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector\venv\Scripts\python.exe'))
$python = $null
foreach ($c in $candidates) { if (-not $python -and (Test-Path $c)) { $python = $c } }
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
}
if (-not $python) { Write-Host 'STOP: no python found (create .venv or run install.ps1)'; exit 1 }
$argList = @((Join-Path $repo 'scripts\run_gates.py'))
if ($Only) { $argList += "--only"; $argList += $Only }
& $python @argList
exit $LASTEXITCODE
