# gen_api_client.ps1 - regenerate the api_client module from the OpenAPI contract (PowerShell 5.1).
# Thin wrapper: scripts/gen_api_client.py (and scripts/codegen/) do the work.
# Rerunning must be a no-op (CLAUDE.md rule 14); scripts/gates/check_codegen.py
# checks that `git diff` over the generated files stays empty.
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
& $python (Join-Path $repo 'scripts\gen_api_client.py')
exit $LASTEXITCODE
