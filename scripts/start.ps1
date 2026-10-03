# start.ps1 - open the ARGUS collector panel from the installed copy (PowerShell 5.1).
# -Console keeps a console window and shows Python errors instead of running hidden.
param([switch]$Console)
$ErrorActionPreference = 'Continue'
$dataDir = Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector'
$appDir = Join-Path $dataDir 'app'
$exe = Join-Path $dataDir 'venv\Scripts\pythonw.exe'
if ($Console) { $exe = Join-Path $dataDir 'venv\Scripts\python.exe' }
if (-not (Test-Path $exe)) { Write-Host "STOP: $exe not found - run scripts\install.ps1 first"; exit 1 }
if (-not (Test-Path (Join-Path $appDir 'VERSION'))) { Write-Host "STOP: $appDir has no VERSION - run scripts\install.ps1 first"; exit 1 }
if ($Console) {
    & $exe -m argus_collector.ui
    exit $LASTEXITCODE
}
Start-Process -FilePath $exe -ArgumentList '-m', 'argus_collector.ui' -WorkingDirectory $appDir
