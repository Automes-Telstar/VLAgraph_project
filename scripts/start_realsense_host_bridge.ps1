param(
    [int]$Port = 9180,
    [int]$Width = 640,
    [int]$Height = 480,
    [int]$Fps = 30,
    [switch]$NoMockFallback
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$healthUrl = "http://localhost:$Port/health"

function Stop-StaleRealSenseBridge {
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) {
        return
    }

    foreach ($listener in $listeners) {
        $processId = [int]$listener.OwningProcess
        if ($processId -le 0 -or $processId -eq $PID) {
            continue
        }

        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        $commandLine = [string]$processInfo.CommandLine
        if ($commandLine -notmatch "realsense_d435i_bridge\.py") {
            Write-Warning "Port $Port is already used by PID $processId, but it does not look like the RealSense bridge. Stop that process or choose another port."
            continue
        }

        Write-Host "Stopping stale RealSense host bridge on port $Port. PID: $processId"
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
    }
}

function Test-RealSenseBridge {
    param(
        [switch]$AcceptStartingBridge
    )
    try {
        $raw = & curl.exe --silent --show-error --max-time 2 $healthUrl
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
            return $false
        }
        $status = $raw | ConvertFrom-Json
        if ($status.source -eq "realsense") {
            return $true
        }
        if ($NoMockFallback) {
            return $false
        }
        return ($AcceptStartingBridge -and $status.ok -eq $true -and $status.service -eq "realsense_d435i_bridge")
    } catch {
        return $false
    }
}

if (Test-RealSenseBridge -AcceptStartingBridge) {
    Write-Host "RealSense host bridge is already running on port $Port."
    exit 0
}

Stop-StaleRealSenseBridge

$pythonCandidates = @(
    (Join-Path $repoRoot "venv\Scripts\python.exe"),
    (Join-Path $repoRoot "clean_env\Scripts\python.exe"),
    "python"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python") {
        $python = $candidate
        break
    }
    if (Test-Path $candidate) {
        $python = $candidate
        break
    }
}

$bridgeScript = Join-Path $repoRoot "scripts\realsense_d435i_bridge.py"
$stdoutLog = Join-Path $repoRoot "scripts\realsense_d435i_bridge.host.out.log"
$stderrLog = Join-Path $repoRoot "scripts\realsense_d435i_bridge.host.err.log"

$args = @(
    $bridgeScript,
    "--host", "0.0.0.0",
    "--port", "$Port",
    "--width", "$Width",
    "--height", "$Height",
    "--fps", "$Fps",
    "--reconnect-interval-sec", "1.0",
    "--frame-cache-ttl-sec", "0.06"
)

if (-not $NoMockFallback) {
    $args += "--mock-when-unavailable"
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList $args `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-RealSenseBridge -AcceptStartingBridge) {
        if (Test-RealSenseBridge) {
            Write-Host "Started RealSense host bridge on port $Port. PID: $($process.Id)"
        } else {
            Write-Host "Started RealSense host bridge on port $Port. PID: $($process.Id). Waiting for real camera frames in the background."
        }
        exit 0
    }
}

Write-Error "RealSense host bridge did not become ready. Check $stderrLog"
