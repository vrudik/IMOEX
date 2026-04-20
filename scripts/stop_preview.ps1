param(
    [int]$Port = 8011
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$previewRoot = Join-Path $env:TEMP "imoex-preview-$Port"
$pidPath = Join-Path $previewRoot "preview.pid"
$serverPidPath = Join-Path $previewRoot "server.pid"
$metadataPath = Join-Path $previewRoot "preview.json"

if (-not (Test-Path $pidPath)) {
    Write-Host "[preview] no PID file found for port $Port"
    exit 0
}

$previewPid = Get-Content -Path $pidPath | Select-Object -First 1
if ($previewPid) {
    $process = Get-Process -Id ([int]$previewPid) -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id
        Write-Host "[preview] stopped PID $previewPid on port $Port"
    } else {
        Write-Host "[preview] process $previewPid is not running"
    }
}

$serverPid = if (Test-Path $serverPidPath) { Get-Content -Path $serverPidPath | Select-Object -First 1 } else { $null }
if ($serverPid) {
    $serverProcess = Get-Process -Id ([int]$serverPid) -ErrorAction SilentlyContinue
    if ($serverProcess) {
        Stop-Process -Id $serverProcess.Id
        Write-Host "[preview] stopped server PID $serverPid on port $Port"
    }
}

Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $serverPidPath -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $metadataPath -ErrorAction SilentlyContinue
