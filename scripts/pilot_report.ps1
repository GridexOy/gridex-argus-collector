# pilot_report.ps1 - the collector side of the pilot report (TZ_TANDEM pair 5) from the installed copy.
# Writes Markdown tables (time, pages, actions, model calls per company; 10 phones checked)
# to %LOCALAPPDATA%\Gridex\ArgusCollector\reports\pilot-<batch or latest>.md and prints the path.
param([string]$Batch = '')
$ErrorActionPreference = 'Stop'
$dataDir = Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector'
$appDir = Join-Path $dataDir 'app'
$exe = Join-Path $dataDir 'venv\Scripts\python.exe'
if (-not (Test-Path $exe)) { Write-Host "STOP: $exe not found - run scripts\install.ps1 first"; exit 1 }
if (-not (Test-Path (Join-Path $dataDir 'state\collector.db'))) { Write-Host "STOP: no collector.db yet - collect a batch first"; exit 1 }
$reports = Join-Path $dataDir 'reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$name = if ($Batch) { "pilot-$Batch.md" } else { 'pilot-latest.md' }
$out = Join-Path $reports $name
$arguments = @('-m', 'argus_collector.pilot', '--out', $out)
if ($Batch) { $arguments += @('--batch', $Batch) }
Push-Location $appDir
try {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { Write-Host "STOP: pilot report failed (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
} finally {
    Pop-Location
}
Write-Host "OK: $out"
