$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"

Write-Host "[scheduler] running due jobs once"
& $python -m apps.worker.runner run-schedule @args | Out-Host
