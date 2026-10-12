param(
    [int]$Port = 9180,
    [int]$Width = 640,
    [int]$Height = 480,
    [int]$Fps = 30,
    [switch]$AllowMockFallback,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$bridgeArgs = @(
    "-Port", "$Port",
    "-Width", "$Width",
    "-Height", "$Height",
    "-Fps", "$Fps"
)

if (-not $AllowMockFallback) {
    $bridgeArgs += "-NoMockFallback"
}

Write-Host "Checking Intel RealSense D435i host bridge on port $Port..."
& (Join-Path $PSScriptRoot "start_realsense_host_bridge.ps1") @bridgeArgs

$composeArgs = @("compose", "up", "-d")
if ($Build) {
    $composeArgs += "--build"
}

Push-Location $repoRoot
try {
    Write-Host "Starting VLA Graph Docker services..."
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($composeArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "VLA Graph is ready. RealSense frame endpoint: http://localhost:$Port/frame"
