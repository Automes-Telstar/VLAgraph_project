param(
  [string]$Task = "Isaac-Cartpole-Direct-v0",
  [int]$NumEnvs = 1,
  [int]$MaxIterations = 200,
  [string]$BridgeRoot = "C:\vlagraph_isaaclab_bridge",
  [string]$TraceDir = "C:\Users\0\Desktop\vlagraph\uploads\motion_traces"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BridgeRoot)) {
  throw "IsaacLab bridge project not found: $BridgeRoot"
}

if (-not (Test-Path $TraceDir)) {
  throw "Motion trace directory not found: $TraceDir"
}

$latest = Get-ChildItem -Path $TraceDir -Filter *.json -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $latest) {
  throw "No motion trace JSON files found in: $TraceDir"
}

Write-Host "Using latest motion trace: $($latest.FullName)"

powershell -ExecutionPolicy Bypass -File "$BridgeRoot\scripts\train_isaaclab.ps1" `
  -Trace $latest.FullName `
  -Task $Task `
  -NumEnvs $NumEnvs `
  -MaxIterations $MaxIterations
