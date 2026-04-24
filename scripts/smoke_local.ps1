$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$smokeRoot = Join-Path $env:TEMP "imoex-smoke-local"
$runId = Get-Date -Format "yyyyMMddHHmmss"
$databasePath = Join-Path $smokeRoot "smoke-$runId.db"
$backupsPath = Join-Path $smokeRoot "backups-$runId"

New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupsPath | Out-Null

$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"
$env:DATABASE_URL = "sqlite:///$($databasePath.Replace('\', '/'))"
$env:BACKUPS_DIR = $backupsPath

Write-Host "[smoke-local] python: $python"
Write-Host "[smoke-local] database: $databasePath"

Write-Host "[smoke-local] running worker recalculate"
& $python -m apps.worker.runner recalculate --root Si | Out-Host

Write-Host "[smoke-local] running worker telegram dry-run"
& $python -m apps.worker.runner notify-telegram --root Si --dry-run | Out-Host

Write-Host "[smoke-local] validating API surface through TestClient"
@'
from fastapi.testclient import TestClient

from apps.api.main import app

with TestClient(app) as client:
    dashboard = client.get("/api/v1/dashboard", params={"root": "Si"})
    dashboard.raise_for_status()
    dashboard_payload = dashboard.json()

    readiness = client.get("/api/v1/health/product-readiness", params={"root": "Si"})
    readiness.raise_for_status()
    readiness_payload = readiness.json()

    preview = client.get("/api/v1/notifications/telegram/preview", params={"root": "Si"})
    preview.raise_for_status()
    preview_payload = preview.json()

    health = client.get("/api/v1/admin/health")
    health.raise_for_status()
    health_payload = health.json()

    assert dashboard_payload["selected_root"] == "Si"
    assert readiness_payload["release_gate"] == "pass"
    assert any(
        item["key"] == "runtime_prompt_governance" and item["status"] == "ok"
        for item in readiness_payload["checks"]
    )
    assert dashboard_payload["recent_signals"]
    assert preview_payload["root"] == "Si"
    assert health_payload["roots_count"] >= 1
    print("[smoke-local] OK")
'@ | & $python -
