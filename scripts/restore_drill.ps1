param(
  [string]$Root = "Si",
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$drillRoot = Join-Path $env:TEMP "imoex-restore-drill"
$runId = Get-Date -Format "yyyyMMddHHmmss"
$sourceDb = Join-Path $drillRoot "source-$runId.db"
$restoredDb = Join-Path $drillRoot "restored-$runId.db"
$backupDir = Join-Path $drillRoot "backups-$runId"
$restoredBackupsDir = Join-Path $drillRoot "restored-backups-$runId"
$backupResultPath = Join-Path $drillRoot "backup-result-$runId.json"

New-Item -ItemType Directory -Force -Path $drillRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
New-Item -ItemType Directory -Force -Path $restoredBackupsDir | Out-Null

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $OutputPath = Join-Path $drillRoot "restore-drill-$runId.json"
}

$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"
$env:DATABASE_URL = "sqlite:///$($sourceDb.Replace('\', '/'))"
$env:BACKUPS_DIR = $backupDir
$env:IMOEX_RESTORE_ROOT = $Root
$env:IMOEX_RESTORE_BACKUP_RESULT = $backupResultPath

function Assert-NativeSuccess {
  param([string]$Name)

  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

Write-Host "[restore-drill] python: $python"
Write-Host "[restore-drill] source database: $sourceDb"
Write-Host "[restore-drill] restored database: $restoredDb"
Write-Host "[restore-drill] output: $OutputPath"

Write-Host "[restore-drill] priming source database"
& $python -m apps.worker.runner recalculate --root $Root | Out-Host
Assert-NativeSuccess "source recalculate"

Write-Host "[restore-drill] creating backup"
@'
from __future__ import annotations

import json
import os
from pathlib import Path

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import AdminBackupRequest

result = get_app_container().maintenance_service.create_backup(AdminBackupRequest(label="restore-drill"))
Path(os.environ["IMOEX_RESTORE_BACKUP_RESULT"]).write_text(
    json.dumps(result.model_dump(mode="json"), indent=2),
    encoding="utf-8",
)
print(result.backup_path)
'@ | & $python -
Assert-NativeSuccess "backup creation"

$backupResult = Get-Content -Path $backupResultPath -Raw | ConvertFrom-Json
$backupPath = [string]$backupResult.backup_path
if (-not (Test-Path $backupPath)) {
  throw "Backup artifact was not created: $backupPath"
}

Write-Host "[restore-drill] restoring backup artifact"
Copy-Item -LiteralPath $backupPath -Destination $restoredDb -Force

$env:DATABASE_URL = "sqlite:///$($restoredDb.Replace('\', '/'))"
$env:BACKUPS_DIR = $restoredBackupsDir
$env:IMOEX_RESTORE_OUTPUT = $OutputPath
$env:IMOEX_RESTORE_BACKUP_PATH = $backupPath
$env:IMOEX_RESTORE_SOURCE_DB = $sourceDb
$env:IMOEX_RESTORE_RESTORED_DB = $restoredDb

Write-Host "[restore-drill] validating restored database"
@'
from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app

root = os.environ.get("IMOEX_RESTORE_ROOT", "Si")
restored_db = Path(os.environ["IMOEX_RESTORE_RESTORED_DB"])
backup_path = Path(os.environ["IMOEX_RESTORE_BACKUP_PATH"])
output_path = Path(os.environ["IMOEX_RESTORE_OUTPUT"])

with sqlite3.connect(restored_db) as conn:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    final_signals = int(conn.execute("SELECT COUNT(*) FROM final_signal").fetchone()[0])
    roots = int(conn.execute("SELECT COUNT(*) FROM root_series").fetchone()[0])

assert integrity == "ok", integrity
assert final_signals > 0, final_signals
assert roots > 0, roots

with TestClient(app) as client:
    signals = client.get("/api/v1/signals", params={"root": root})
    signals.raise_for_status()
    signals_payload = signals.json()

    readiness = client.get("/api/v1/health/product-readiness", params={"root": root})
    readiness.raise_for_status()
    readiness_payload = readiness.json()

    admin_health = client.get("/api/v1/admin/health")
    admin_health.raise_for_status()
    admin_payload = admin_health.json()

assert signals_payload, signals_payload
assert readiness_payload["release_gate"] == "pass", readiness_payload
assert admin_payload["database_status"] == "ok", admin_payload
assert admin_payload["roots_count"] >= 1, admin_payload

summary = {
    "generated_at": datetime.now(UTC).isoformat(),
    "root": root,
    "backup_path": str(backup_path),
    "restored_database": str(restored_db),
    "integrity_check": integrity,
    "roots": roots,
    "final_signals": final_signals,
    "release_gate": readiness_payload["release_gate"],
    "admin_status": admin_payload["status"],
}
output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
'@ | & $python -
Assert-NativeSuccess "restore validation"

Write-Host "[restore-drill] OK"
