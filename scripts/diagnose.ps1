# diagnose.ps1 - ARGUS collector machine check (Windows PowerShell 5.1).
# Prints Windows, Chrome, NVIDIA, RAM, disk and local model lines with explicit
# states (never "unknown"). -Json prints the argus-collector-diagnose/1 document
# that the panel parses; the state rules match argus_collector.diagnostics.
param(
    [switch]$Json,
    [string]$ModelEndpoint = 'http://127.0.0.1:8080'
)

# 'Continue': PS 5.1 turns native stderr into terminating errors under 'Stop';
# every probe below handles its own failure and reports an explicit state.
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$DiskLowPct = 85
$GpuModelMinUsedMb = 1024

function Get-Catalogue {
    $path = Join-Path $PSScriptRoot '..\collector\messages\fi.json'
    if (-not (Test-Path $path)) { return $null }
    return (Get-Content -Path $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-Msg([string]$Key, [hashtable]$Params = @{}) {
    $text = $null
    if ($script:Catalogue -ne $null) { $text = $script:Catalogue.$Key }
    if (-not $text) { $text = $Key }
    foreach ($name in $Params.Keys) { $text = $text.Replace('{' + $name + '}', [string]$Params[$name]) }
    return $text
}

function Get-OsFacts {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    if (-not $os) { return @{ name = 'Windows (Win32_OperatingSystem not readable)'; version = [string][Environment]::OSVersion.Version } }
    return @{ name = [string]$os.Caption; version = [string]$os.Version }
}

function Get-ChromePath {
    $keys = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
              'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe')
    foreach ($key in $keys) {
        if (Test-Path $key) {
            $p = (Get-ItemProperty -Path $key).'(default)'
            if ($p -and (Test-Path $p)) { return [string]$p }
        }
    }
    $known = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
               "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
               "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe")
    foreach ($p in $known) { if ($p -and (Test-Path $p)) { return $p } }
    return ''
}

function Get-ChromeFacts {
    $path = Get-ChromePath
    $version = ''
    if ($path) { $version = [string](Get-Item $path).VersionInfo.ProductVersion }
    $state = 'missing'
    if ($path) { $state = 'available' }
    return @{ path = $path; version = $version; state = $state }
}

function Get-GpuFacts {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($smi) {
        $line = $null
        try {
            $line = & $smi.Source --query-gpu=name,driver_version,memory.total,memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1
        } catch { $line = $null }
        if ($LASTEXITCODE -eq 0 -and $line) {
            $parts = $line.Split(',') | ForEach-Object { $_.Trim() }
            return @{ name = $parts[0]; driver = $parts[1]; memory_total_mb = [int]$parts[2];
                      memory_used_mb = [int]$parts[3]; source = 'nvidia-smi'; state = 'nvidia' }
        }
    }
    $adapter = Get-CimInstance Win32_VideoController | Where-Object { $_.Name } | Select-Object -First 1
    if (-not $adapter) {
        return @{ name = ''; driver = ''; memory_total_mb = 0; memory_used_mb = 0; source = 'none'; state = 'missing' }
    }
    $state = 'other'
    if ($adapter.Name -match 'NVIDIA') { $state = 'nvidia' }
    $totalMb = 0
    if ($adapter.AdapterRAM) { $totalMb = [int]([math]::Round($adapter.AdapterRAM / 1MB)) }
    return @{ name = [string]$adapter.Name; driver = [string]$adapter.DriverVersion; memory_total_mb = $totalMb;
              memory_used_mb = 0; source = 'wmi'; state = $state }
}

function Get-MemoryFacts {
    $os = Get-CimInstance Win32_OperatingSystem
    return @{ total_mb = [int]($os.TotalVisibleMemorySize / 1024); free_mb = [int]($os.FreePhysicalMemory / 1024) }
}

function Get-DiskFacts {
    $drive = Get-PSDrive -Name ($env:SystemDrive.TrimEnd(':'))
    $totalGb = [math]::Round(($drive.Used + $drive.Free) / 1GB, 1)
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    $usedPct = 0
    if ($totalGb -gt 0) { $usedPct = [int][math]::Round(($totalGb - $freeGb) * 100 / $totalGb) }
    $state = 'ok'
    if ($usedPct -gt $DiskLowPct) { $state = 'low' }
    return @{ path = $env:SystemDrive; total_gb = $totalGb; free_gb = $freeGb; used_pct = $usedPct; state = $state }
}

function Get-ModelFacts([hashtable]$Gpu) {
    $reachable = $false
    $detail = ''
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri ($ModelEndpoint.TrimEnd('/') + '/health') -TimeoutSec 2
        $reachable = [int]$resp.StatusCode -lt 500
        $detail = 'HTTP ' + $resp.StatusCode
    } catch {
        $errResp = $_.Exception.Response
        if ($errResp -and [int]$errResp.StatusCode -lt 500) {
            $reachable = $true
            $detail = 'HTTP ' + [int]$errResp.StatusCode
        } else {
            $detail = 'no answer: ' + $_.Exception.Message
        }
    }
    $state = 'none'
    if ($reachable) {
        $state = 'cpu'
        if ($Gpu.state -eq 'nvidia' -and $Gpu.memory_used_mb -ge $GpuModelMinUsedMb) { $state = 'gpu' }
    }
    return @{ endpoint = $ModelEndpoint; reachable = $reachable; detail = $detail; state = $state }
}

function Write-Lines([hashtable]$Doc) {
    $gpu = $Doc.gpu
    Write-Output (Get-Msg 'resources.os' @{ name = $Doc.os.name; version = $Doc.os.version })
    if ($Doc.chrome.state -eq 'available') { Write-Output ((Get-Msg 'resources.chrome.ok') + ' (' + $Doc.chrome.version + ')') }
    else { Write-Output (Get-Msg 'resources.chrome.missing') }
    switch ($gpu.state) {
        'nvidia' { Write-Output (Get-Msg 'resources.gpu.nvidia' @{ name = $gpu.name; driver = $gpu.driver }) }
        'other' { Write-Output (Get-Msg 'resources.gpu.other' @{ name = $gpu.name }) }
        default { Write-Output (Get-Msg 'resources.gpu.missing') }
    }
    if ($gpu.memory_total_mb -gt 0) {
        Write-Output (Get-Msg 'resources.gpuMemory' @{ used = $gpu.memory_used_mb; total = $gpu.memory_total_mb })
    }
    $mem = $Doc.memory
    Write-Output (Get-Msg 'resources.memory' @{ free = [math]::Round($mem.free_mb / 1024, 1); total = [math]::Round($mem.total_mb / 1024, 1) })
    $disk = $Doc.disk
    Write-Output (Get-Msg 'resources.disk' @{ path = $disk.path; free = $disk.free_gb; pct = $disk.used_pct })
    if ($disk.state -eq 'low') { Write-Output (Get-Msg 'resources.diskWarning') }
    switch ($Doc.model.state) {
        'gpu' { Write-Output (Get-Msg 'resources.model.gpu') }
        'cpu' { Write-Output (Get-Msg 'resources.model.cpu') }
        default { Write-Output ((Get-Msg 'resources.model.none') + ' (' + $Doc.model.endpoint + ': ' + $Doc.model.detail + ')') }
    }
}

$script:Catalogue = Get-Catalogue
$gpuFacts = Get-GpuFacts
$doc = @{
    schema = 'argus-collector-diagnose/1'
    source = 'diagnose.ps1'
    os = Get-OsFacts
    chrome = Get-ChromeFacts
    gpu = $gpuFacts
    memory = Get-MemoryFacts
    disk = Get-DiskFacts
    model = Get-ModelFacts $gpuFacts
}
if ($Json) { Write-Output ($doc | ConvertTo-Json -Depth 4) } else { Write-Lines $doc }
