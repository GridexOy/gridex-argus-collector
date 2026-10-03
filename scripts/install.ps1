# install.ps1 - install the ARGUS collector on this Windows PC (PowerShell 5.1).
# Refuses a dirty tree, a branch other than main and any red gate.
# Result: %LOCALAPPDATA%\Gridex\ArgusCollector\{app,venv,state,browser-profile,logs,build.json}
# plus a desktop shortcut "ARGUS Selain" that runs scripts\start.ps1.
# Native commands (git, pip, robocopy) are checked by exit code, so the
# preference stays 'Continue' (PS 5.1 turns stderr into errors under 'Stop');
# cmdlets that must not fail silently carry -ErrorAction Stop.
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Stop-Install([string]$Reason) {
    Write-Host ('STOP: ' + $Reason)
    exit 1
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..') -ErrorAction Stop).Path
Set-Location $repo
$dataDir = Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector'
$appDir = Join-Path $dataDir 'app'
$venvDir = Join-Path $dataDir 'venv'

# --- 1. git: main, clean tree ------------------------------------------------
$inside = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $inside -ne 'true') { Stop-Install "$repo is not a git work tree" }
$branch = git rev-parse --abbrev-ref HEAD
if ($branch -ne 'main') { Stop-Install "install only from main (current branch: $branch)" }
$dirty = git status --porcelain
if ($dirty) { Stop-Install "work tree is dirty, commit or stash first:`n$($dirty -join "`n")" }
$commit = git rev-parse --short HEAD

# --- 2. VERSION ---------------------------------------------------------------
$version = (Get-Content -Path (Join-Path $repo 'VERSION') -Raw -ErrorAction Stop).Trim()
if ($version -notmatch '^0\.\d+\.\d+\.\d+$') { Stop-Install "VERSION must be 0.<stage>.<step>.<fix>, got '$version'" }

# --- 3. Python 3.12 ------------------------------------------------------------
$python = $null
$launcher = Get-Command py -ErrorAction SilentlyContinue
if ($launcher) {
    $probe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) { $python = $probe.Trim() }
}
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $ver = & $cmd.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($ver -eq '3.12') { $python = $cmd.Source }
    }
}
if (-not $python) { Stop-Install 'Python 3.12 not found (install from python.org with tcl/tk, then rerun)' }
& $python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) { Stop-Install 'Python 3.12 has no tkinter; reinstall with the tcl/tk option' }
Write-Host "python: $python"

# --- 4. venv with pinned dependencies ----------------------------------------
New-Item -ItemType Directory -Force -Path $dataDir, (Join-Path $dataDir 'state'), (Join-Path $dataDir 'browser-profile'), (Join-Path $dataDir 'logs') -ErrorAction Stop | Out-Null
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Stop-Install 'venv creation failed' }
}
& $venvPython -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) { Stop-Install 'pip upgrade failed' }
& $venvPython -m pip install --quiet -r (Join-Path $repo 'requirements.txt') -r (Join-Path $repo 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { Stop-Install 'dependency install failed (see pip output above)' }
# Chrome channel "chrome" uses the installed Google Chrome: no `playwright install` here.

# --- 5. gates and tests in the source tree -----------------------------------
& $venvPython (Join-Path $repo 'scripts\run_gates.py')
if ($LASTEXITCODE -ne 0) { Stop-Install 'a gate is red - nothing installed' }
& $venvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { Stop-Install 'tests failed - nothing installed' }

# --- 6. copy the tree to the app dir -----------------------------------------
$excludeDirs = @('.git', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache', 'test-results')
$excludeFiles = @('STOP', 'config.yaml', '.env')
robocopy $repo $appDir /MIR /NFL /NDL /NJH /NJS /NP /XD $excludeDirs /XF $excludeFiles | Out-Null
if ($LASTEXITCODE -ge 8) { Stop-Install "robocopy failed with code $LASTEXITCODE" }
& $venvPython -m pip install --quiet --no-deps -e $appDir
if ($LASTEXITCODE -ne 0) { Stop-Install 'editable install of the app failed' }

# --- 7. build info for the panel ---------------------------------------------
$build = @{ version = $version; commit = $commit; built_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz') }
$build | ConvertTo-Json | Set-Content -Path (Join-Path $dataDir 'build.json') -Encoding UTF8 -ErrorAction Stop
if (-not (Test-Path (Join-Path $dataDir 'config.yaml'))) {
    Copy-Item (Join-Path $repo 'config.example.yaml') (Join-Path $dataDir 'config.yaml') -ErrorAction Stop
}

# --- 8. desktop shortcut -----------------------------------------------------
$startScript = Join-Path $appDir 'scripts\start.ps1'
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'ARGUS Selain.lnk'))
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`""
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = "ARGUS Selain cv$version"
$shortcut.Save()

Write-Host "installed cv$version ($commit) into $appDir"
Write-Host "start: $startScript  (desktop shortcut 'ARGUS Selain')"
& (Join-Path $appDir 'scripts\diagnose.ps1')
