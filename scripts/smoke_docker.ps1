$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot "infra\docker\docker-compose.yml"

docker compose -f $composeFile up --build -d postgres api

try {
  Write-Host "[smoke-docker] waiting for API readiness"
  $ready = $false
  for ($i = 0; $i -lt 30; $i++) {
    try {
      $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health/ready" -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -eq 200) {
        $ready = $true
        break
      }
    } catch {
      Start-Sleep -Seconds 2
    }
  }

  if (-not $ready) {
    throw "API did not become ready in time."
  }

  $dashboard = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/dashboard?root=Si" -UseBasicParsing -TimeoutSec 10
  if ($dashboard.StatusCode -ne 200) {
    throw "Dashboard smoke request failed."
  }

  Write-Host "[smoke-docker] OK"
} finally {
  docker compose -f $composeFile down
}
