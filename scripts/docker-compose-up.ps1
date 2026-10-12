param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

& (Join-Path $PSScriptRoot "start_realsense_host_bridge.ps1") -NoMockFallback

$composeArgs = @("compose", "up", "--build")
if ($Detached) {
    $composeArgs += "-d"
}

Push-Location $repoRoot
try {
    & docker @composeArgs
} finally {
    Pop-Location
}
