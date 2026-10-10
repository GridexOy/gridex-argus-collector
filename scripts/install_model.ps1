# install_model.ps1 - the local model on this PC (Windows PowerShell 5.1, ASCII only).
# Installs Ollama when missing; sets OLLAMA_CONTEXT_LENGTH; pulls the card model (14b) -
# the only model of the collector since 6.1 (TZ_SELAIN v4.0 4.1), so no second model is
# ever loaded and OLLAMA_MAX_LOADED_MODELS is not needed; checks nvidia-smi and
# that the card model runs on the GPU. Downloads go through curl.exe (the WinHTTP proxy
# is broken here); when curl fails it prints the URL and path to fetch by hand.
param(
    [string]$ModelName = 'qwen2.5:14b-instruct',
    [string]$Endpoint = 'http://127.0.0.1:11434/v1',
    [int]$ContextLength = 16384
)
$ErrorActionPreference = 'Continue'
$OllamaSetupUrl = 'https://ollama.com/download/OllamaSetup.exe'
$GgufPage = 'https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/tree/main'
$GgufFile = 'Qwen2.5-14B-Instruct-Q4_K_M.gguf'
$dataDir = Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector'
$modelsDir = Join-Path $dataDir 'models'
$setupPath = Join-Path $env:TEMP 'OllamaSetup.exe'

function Stop-Script([string]$Reason, [int]$Code = 1) {
    Write-Host ('STOP: ' + $Reason)
    exit $Code
}

function Invoke-Direct([string]$Url, [string]$Method = 'GET', [string]$Body = $null, [int]$TimeoutSec = 10) {
    # Loopback call without the system proxy (WinHTTP proxy answers 127.0.0.1 with 502).
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.Method = $Method
        $req.Proxy = $null
        $req.Timeout = $TimeoutSec * 1000
        $req.ReadWriteTimeout = $TimeoutSec * 1000
        if ($Body) {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
            $req.ContentType = 'application/json'
            $req.ContentLength = $bytes.Length
            $stream = $req.GetRequestStream()
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Close()
        }
        $resp = $req.GetResponse()
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $text = $reader.ReadToEnd()
        $reader.Close()
        $resp.Close()
        return $text
    } catch {
        return $null
    }
}

function Test-Gpu {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { Write-Host 'WARNING: nvidia-smi not found - the model will run on the CPU'; return '' }
    # Collect all output first: '| Select-Object -First 1' stops the native
    # process early in PS 5.1 and leaves a non-zero $LASTEXITCODE.
    $out = @(& $smi.Source --query-gpu=name,driver_version,memory.total,memory.used --format=csv,noheader,nounits 2>&1)
    $line = $out | Where-Object { "$_" -match ',' } | Select-Object -First 1
    if (-not $line) {
        Write-Host 'WARNING: nvidia-smi gave no GPU line - the model may run on the CPU. nvidia-smi said:'
        $out | ForEach-Object { Write-Host ('  ' + $_) }
        return ''
    }
    Write-Host ('gpu: ' + $line)
    return "$line"
}

function Get-OllamaExe {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $known = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $known) { return $known }
    return ''
}

function Get-OllamaSetup {
    if (Test-Path $setupPath) { Write-Host ('using ' + $setupPath); return }
    Write-Host ('downloading ' + $OllamaSetupUrl)
    & curl.exe -L --fail --silent --show-error -o $setupPath $OllamaSetupUrl
    if ($LASTEXITCODE -eq 0 -and (Test-Path $setupPath)) { return }
    Write-Host 'curl.exe could not download the Ollama installer.'
    Write-Host ('  1. Open in the browser: ' + $OllamaSetupUrl)
    Write-Host ('  2. Save the file as:    ' + $setupPath)
    Write-Host '  3. Run this script again.'
    Stop-Script 'Ollama installer missing' 2
}

function Install-Ollama {
    Get-OllamaSetup
    Write-Host 'installing Ollama (silent)'
    $proc = Start-Process -FilePath $setupPath -ArgumentList '/VERYSILENT', '/NORESTART' -Wait -PassThru
    if ($proc.ExitCode -ne 0) { Stop-Script ('Ollama installer exit code ' + $proc.ExitCode) }
    $exe = Get-OllamaExe
    if (-not $exe) { Stop-Script 'Ollama installed but ollama.exe not found; log out and in, then rerun' }
    return $exe
}

function Set-OllamaVariable([string]$Name, [string]$Value) {
    $current = [Environment]::GetEnvironmentVariable($Name, 'User')
    Set-Item -Path ('env:' + $Name) -Value $Value
    if ($current -eq $Value) { return $false }
    [Environment]::SetEnvironmentVariable($Name, $Value, 'User')
    Write-Host ($Name + ' set to ' + $Value + ' (user environment)')
    return $true
}

function Set-OllamaContext {
    # 4k context by default, the walk sends ~6k tokens. One model is loaded (6.1), so
    # OLLAMA_MAX_LOADED_MODELS and OLLAMA_NUM_PARALLEL are left to Ollama's defaults.
    return (Set-OllamaVariable 'OLLAMA_CONTEXT_LENGTH' ([string]$ContextLength))
}

function Start-OllamaServer([string]$Exe, [bool]$Restart) {
    $modelsUrl = $Endpoint.TrimEnd('/') + '/models'
    if ($Restart) {
        Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    if (-not (Invoke-Direct $modelsUrl)) {
        Write-Host 'starting ollama serve'
        Start-Process -FilePath $Exe -ArgumentList 'serve' -WindowStyle Hidden
    }
    for ($i = 0; $i -lt 30; $i++) {
        if (Invoke-Direct $modelsUrl) { Write-Host ('ollama answers at ' + $modelsUrl); return }
        Start-Sleep -Seconds 1
    }
    Stop-Script ('ollama does not answer at ' + $modelsUrl)
}

function Install-FromGguf([string]$Exe) {
    New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
    $gguf = Get-ChildItem -Path $modelsDir -Filter '*.gguf' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $gguf) {
        Write-Host 'ollama pull failed and no GGUF file is present.'
        Write-Host ('  1. Open in the browser: ' + $GgufPage)
        Write-Host ('  2. Download ' + $GgufFile + ' into: ' + $modelsDir)
        Write-Host '  3. Run this script again.'
        Stop-Script 'model missing' 3
    }
    $modelfile = Join-Path $modelsDir 'Modelfile'
    $lines = @(('FROM ' + $gguf.FullName), ('PARAMETER num_ctx ' + $ContextLength), 'PARAMETER temperature 0')
    [System.IO.File]::WriteAllLines($modelfile, $lines, (New-Object System.Text.ASCIIEncoding))
    Write-Host ('creating ' + $ModelName + ' from ' + $gguf.FullName)
    & $Exe create $ModelName -f $modelfile
    if ($LASTEXITCODE -ne 0) { Stop-Script 'ollama create failed' }
}

function Install-Model([string]$Exe) {
    $listed = Invoke-Direct ($Endpoint.TrimEnd('/') + '/models')
    if ($listed -and ($listed -match ('"' + [regex]::Escape($ModelName) + '(:latest)?"'))) {
        Write-Host ('model already present: ' + $ModelName)
        return
    }
    Write-Host ('pulling ' + $ModelName + ' (several GB, one time)')
    & $Exe pull $ModelName
    if ($LASTEXITCODE -eq 0) { return }
    Install-FromGguf $Exe
}

function Test-ModelOnGpu([string]$Exe) {
    $body = '{"model":"' + $ModelName + '","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":5,"temperature":0}'
    $reply = Invoke-Direct ($Endpoint.TrimEnd('/') + '/chat/completions') 'POST' $body 300
    if (-not $reply) { Stop-Script 'the model did not answer a test completion (see ollama logs)' }
    Write-Host 'test completion answered'
    $ps = & $Exe ps 2>$null | Out-String
    Write-Host $ps
    if ($ps -match '100% GPU') { Write-Host 'ollama runs the model fully on the GPU' }
    elseif ($ps -match 'GPU') { Write-Host 'WARNING: the model is only partly on the GPU; a smaller model or context may be needed' }
    else { Write-Host 'WARNING: ollama ps shows no GPU use; check the NVIDIA driver and ollama logs' }
    $after = @(& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null) | Select-Object -First 1
    Write-Host ('gpu memory used now: ' + $after + ' MB')
}

Test-Gpu | Out-Null
$ollama = Get-OllamaExe
if (-not $ollama) { $ollama = Install-Ollama } else { Write-Host ('ollama: ' + $ollama) }
$changed = Set-OllamaContext
Start-OllamaServer $ollama $changed
Install-Model $ollama
Test-ModelOnGpu $ollama
Write-Host ('done: ' + $ModelName + ' at ' + $Endpoint)
Write-Host 'the panel shows Malli: paikallinen (GPU) and the Reititys line in Resurssit after this
