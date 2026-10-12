param(
    [string]$IsaacGrootPath = "",
    [string]$PolicyHost = "127.0.0.1",
    [int]$PolicyPort = 5555,
    [int]$AdapterPort = 9072
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$adapterDir = Join-Path $repoRoot "services\gr00t_policy_adapter"

$placeholderPathPattern = "path\\to|실제|경로|example|YOUR_"
if ($IsaacGrootPath -and ($IsaacGrootPath -match $placeholderPathPattern)) {
    throw @"
Isaac-GR00T path is still a placeholder: $IsaacGrootPath

Use the real local folder that contains the NVIDIA Isaac-GR00T repository.
Example after cloning:
  -IsaacGrootPath "C:\Users\0\Desktop\Isaac-GR00T"

If you have not installed it yet:
  git clone --recurse-submodules https://github.com/NVIDIA/Isaac-GR00T C:\Users\0\Desktop\Isaac-GR00T
"@
}

if ($IsaacGrootPath -and (Test-Path $IsaacGrootPath)) {
    $resolvedIsaacGrootPath = Resolve-Path $IsaacGrootPath
    $env:PYTHONPATH = "$resolvedIsaacGrootPath;$env:PYTHONPATH"
    Write-Host "Using Isaac-GR00T path: $resolvedIsaacGrootPath"
} elseif ($IsaacGrootPath) {
    throw @"
Isaac-GR00T path not found: $IsaacGrootPath

Pass the real local folder that contains the NVIDIA Isaac-GR00T repository.
Example:
  .\scripts\run_gr00t_policy_adapter.ps1 -IsaacGrootPath "C:\Users\0\Desktop\Isaac-GR00T" -PolicyHost "127.0.0.1" -PolicyPort 5555 -AdapterPort 9072
"@
} else {
    Write-Host "No Isaac-GR00T path provided. Expecting gr00t to be importable in the current Python environment."
}

$env:GR00T_POLICY_HOST = $PolicyHost
$env:GR00T_POLICY_PORT = [string]$PolicyPort

Push-Location $adapterDir
try {
    python -m pip install -r requirements.txt
    python -m uvicorn gr00t_http_adapter:app --host 0.0.0.0 --port $AdapterPort
} finally {
    Pop-Location
}
