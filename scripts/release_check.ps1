param(
  [string]$Root = "Si",
  [switch]$SkipFullPytest,
  [switch]$SkipDocker,
  [switch]$SkipPerformance,
  [switch]$SkipRestore,
  [switch]$SkipBrowser,
  [string]$BrowserChannel = "",
  [switch]$EnforcePerformanceBudgets,
  [switch]$AllowTrackedLocalArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$releaseRoot = Join-Path $env:TEMP "imoex-release-check"
$runId = Get-Date -Format "yyyyMMddHHmmss"
$databasePath = Join-Path $releaseRoot "release-$runId.db"
$backupsPath = Join-Path $releaseRoot "backups-$runId"

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupsPath | Out-Null

$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"
$env:DATABASE_URL = "sqlite:///$($databasePath.Replace('\', '/'))"
$env:BACKUPS_DIR = $backupsPath
$env:IMOEX_RELEASE_ROOT = $Root

Write-Host "[release-check] python: $python"
Write-Host "[release-check] database: $databasePath"

function Invoke-ReleaseStep {
  param(
    [string]$Name,
    [scriptblock]$Step
  )

  Write-Host "[release-check] $Name"
  & $Step
}

function Assert-NativeSuccess {
  param([string]$Name)

  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

Invoke-ReleaseStep "checking tracked local artifacts" {
  $trackedArtifacts = & git -C $repoRoot ls-files ".smoke-*.db" ".smoke-*.db-journal" ".office-cleanup-backup-*"
  if ($trackedArtifacts) {
    $message = "Release check found tracked local artifacts: $($trackedArtifacts -join ', ')"
    if ($AllowTrackedLocalArtifacts) {
      Write-Warning "$message. Continuing because -AllowTrackedLocalArtifacts was set."
    } else {
      throw "$message"
    }
  }
}

if ($SkipFullPytest) {
Invoke-ReleaseStep "running focused release tests" {
    & $python -m pytest tests\test_alembic_migrations.py tests\test_api_health.py tests\test_api_dashboard.py tests\test_dashboard_formatting.py tests\test_marketdata_service.py tests\test_maintenance_backup.py tests\test_security_admin.py tests\test_release_readiness_assets.py tests\test_private_beta_evidence_validation.py -q
    Assert-NativeSuccess "focused release tests"
  }
} else {
  Invoke-ReleaseStep "running full pytest suite" {
    & $python -m pytest tests -q
    Assert-NativeSuccess "full pytest suite"
  }
}

Invoke-ReleaseStep "running local smoke" {
  powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\smoke_local.ps1")
  Assert-NativeSuccess "local smoke"
}

if (-not $SkipPerformance) {
  Invoke-ReleaseStep "capturing performance baseline" {
    $performanceArgs = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $repoRoot "scripts\performance_baseline.ps1"), "-Root", $Root)
    if ($EnforcePerformanceBudgets) {
      $performanceArgs += "-FailOnBudget"
    }
    powershell @performanceArgs
    Assert-NativeSuccess "performance baseline"
  }
}

if (-not $SkipRestore) {
  Invoke-ReleaseStep "running backup restore drill" {
    powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\restore_drill.ps1") -Root $Root
    Assert-NativeSuccess "backup restore drill"
  }
}

if (-not $SkipBrowser) {
  Invoke-ReleaseStep "running browser smoke" {
    $browserArgs = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $repoRoot "scripts\browser_smoke.ps1"), "-Root", $Root)
    if (-not [string]::IsNullOrWhiteSpace($BrowserChannel)) {
      $browserArgs += @("-Channel", $BrowserChannel)
    }
    powershell @browserArgs
    Assert-NativeSuccess "browser smoke"
  }
}

Invoke-ReleaseStep "priming release validation database" {
  & $python -m apps.worker.runner recalculate --root $Root | Out-Host
  Assert-NativeSuccess "release validation recalculate"
}

Invoke-ReleaseStep "validating product readiness and admin health" {
@'
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from apps.api.main import app

root = os.environ.get("IMOEX_RELEASE_ROOT", "Si")

with TestClient(app) as client:
    readiness = client.get("/api/v1/health/product-readiness", params={"root": root})
    readiness.raise_for_status()
    readiness_payload = readiness.json()
    assert readiness_payload["release_gate"] == "pass", readiness_payload

    admin_health = client.get("/api/v1/admin/health")
    admin_health.raise_for_status()
    admin_payload = admin_health.json()
    assert admin_payload["status"] in {"ok", "degraded"}, admin_payload
    assert admin_payload["roots_count"] >= 1, admin_payload

    preview = client.get("/api/v1/notifications/telegram/preview", params={"root": root})
    preview.raise_for_status()
    preview_payload = preview.json()
    assert preview_payload["root"] == root, preview_payload

print("[release-check] product readiness OK")
'@ | & $python -
  Assert-NativeSuccess "product readiness validation"
}

if (-not $SkipDocker) {
  Invoke-ReleaseStep "running docker smoke" {
    powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\smoke_docker.ps1")
    Assert-NativeSuccess "docker smoke"
  }
}

Write-Host "[release-check] OK"
