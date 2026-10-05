# walk_timing.ps1 - where the collecting time went, from a collector journal (PowerShell 5.1).
# Splits logs\collector-<date>.log into page phases (load, snapshot, extract, cards, bind,
# record, next step), who decided (rules / each model), model calls and delivery, per company,
# and writes %LOCALAPPDATA%\Gridex\ArgusCollector\reports\timing-<date>.md. Logs older than
# 0.4.8.0 have no phase lines: then only model calls and the time between pages are shown.
param([string]$Log = '')
$ErrorActionPreference = 'Stop'
$dataDir = Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector'
$appDir = Join-Path $dataDir 'app'
$exe = Join-Path $dataDir 'venv\Scripts\python.exe'
if (-not (Test-Path $exe)) { Write-Host "STOP: $exe not found - run scripts\install.ps1 first"; exit 1 }
if (-not $Log) { $Log = Join-Path $dataDir ('logs\collector-' + (Get-Date -Format 'yyyy-MM-dd') + '.log') }
if (-not (Test-Path $Log)) { Write-Host "STOP: no log $Log"; exit 1 }
$reports = Join-Path $dataDir 'reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$out = Join-Path $reports ('timing-' + [System.IO.Path]::GetFileNameWithoutExtension($Log) + '.md')
Push-Location $appDir
try {
    & $exe -m argus_collector.pilot timing --log $Log --out $out
    if ($LASTEXITCODE -ne 0) { Write-Host "STOP: timing report failed (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
} finally {
    Pop-Location
}
Write-Host "OK: $out"
