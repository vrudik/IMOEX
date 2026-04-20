param(
    [int]$Port = 8011,
    [string]$Root = "Si",
    [switch]$SkipWarmup
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$previewRoot = Join-Path $env:TEMP "imoex-preview-$Port"
$databasePath = Join-Path $previewRoot "preview.db"

Write-Host "[preview] python: $python"
Write-Host "[preview] root: $Root"
Write-Host "[preview] database: $databasePath"
Write-Host "[preview] workspace: http://127.0.0.1:$Port/workspace?root=$Root"
Write-Host "[preview] dashboard: http://127.0.0.1:$Port/dashboard?root=$Root"

Write-Host "[preview] starting uvicorn on 127.0.0.1:$Port"
$arguments = @("-m", "apps.preview_runner", "--port", "$Port", "--root", $Root)
if ($SkipWarmup) {
    $arguments += "--skip-warmup"
}
Push-Location $repoRoot
try {
    & $python @arguments
} finally {
    Pop-Location
}
