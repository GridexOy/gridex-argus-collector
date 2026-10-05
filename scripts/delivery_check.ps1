# delivery_check.ps1 - why ARGUS refused, from the collector side (PowerShell 5.1, 0.4.8.1).
# 1) every rejected event / snapshot from the local outbox: company, event_id or evidence_id,
#    seq, code and its words -> %LOCALAPPDATA%\Gridex\ArgusCollector\reports\rejected-<date>.md;
# 2) the journal lines of the last $Minutes minutes about refusals: delivery HTTP errors (with
#    ARGUS's request_id for the API journal), rejected items, heartbeat answer changes.
# Reads local files only; sends nothing and shows no token or contact value.
param([int]$Minutes = 30)
# Native commands are checked by exit code (PS 5.1 turns their stderr into errors under 'Stop').
$ErrorActionPreference = 'Continue'
$dataDir = Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector'
$appDir = Join-Path $dataDir 'app'
$exe = Join-Path $dataDir 'venv\Scripts\python.exe'
if (-not (Test-Path $exe)) { Write-Host "STOP: $exe not found - run scripts\install.ps1 first"; exit 1 }
$reports = Join-Path $dataDir 'reports'
New-Item -ItemType Directory -Force -Path $reports -ErrorAction Stop | Out-Null
$out = Join-Path $reports ('rejected-' + (Get-Date -Format 'yyyy-MM-dd-HHmm') + '.md')
Push-Location $appDir -ErrorAction Stop
try {
    & $exe -m argus_collector.pilot rejected --out $out
    if ($LASTEXITCODE -ne 0) { Write-Host "STOP: rejected list failed (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
} finally {
    Pop-Location
}
Get-Content -Path $out -Encoding UTF8 -ErrorAction Stop | Select-Object -First 40
$log = Join-Path $dataDir ('logs\collector-' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd') + '.log')
if (-not (Test-Path $log)) { Write-Host "No journal for today: $log"; exit 0 }
$since = (Get-Date).ToUniversalTime().AddMinutes(-$Minutes)
$pattern = ' (delivery: .*(rejected [a-z]|HTTP \d)|http: (heartbeat|claim|reconcile))'
Write-Host "Journal since $($since.ToString('HH:mm')) UTC: $log"
foreach ($line in (Get-Content -Path $log -Encoding UTF8 -ErrorAction Stop)) {
    if ($line -notmatch $pattern) { continue }
    $stamp = [DateTime]::MinValue
    $ok = [DateTime]::TryParse($line.Split(' ')[0], [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AdjustToUniversal, [ref]$stamp)
    if ($ok -and $stamp -ge $since) { Write-Host $line }
}
Write-Host "OK: $out"
