param(
  [string]$SourceDatabaseUrl = "",
  [string]$RestoredDatabaseUrl = "",
  [string]$Root = "Si",
  [string]$BackupPath = "",
  [string]$OutputPath = "",
  [switch]$AllowDestructiveRestore
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($SourceDatabaseUrl)) {
  $SourceDatabaseUrl = $env:DATABASE_URL
}
if ([string]::IsNullOrWhiteSpace($SourceDatabaseUrl)) {
  throw "SourceDatabaseUrl or DATABASE_URL is required."
}
if ([string]::IsNullOrWhiteSpace($RestoredDatabaseUrl)) {
  throw "RestoredDatabaseUrl is required and must point to a fresh disposable Postgres database."
}
if (-not $AllowDestructiveRestore) {
  throw "Refusing to run pg_restore without -AllowDestructiveRestore. Use a fresh disposable target database."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$drillRoot = Join-Path $env:TEMP "imoex-postgres-restore-drill"
$runId = Get-Date -Format "yyyyMMddHHmmss"
$backupDir = Join-Path $drillRoot "backups-$runId"
$backupResultPath = Join-Path $drillRoot "postgres-backup-result-$runId.json"

New-Item -ItemType Directory -Force -Path $drillRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $OutputPath = Join-Path $drillRoot "postgres-restore-drill-$runId.json"
}

$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"
$env:IMOEX_RESTORE_ROOT = $Root
$env:IMOEX_RESTORE_OUTPUT = $OutputPath
$env:IMOEX_RESTORE_BACKUP_RESULT = $backupResultPath
$env:IMOEX_RESTORE_TARGET_DATABASE_URL = $RestoredDatabaseUrl

function Assert-NativeSuccess {
  param([string]$Name)

  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

Write-Host "[postgres-restore-drill] python: $python"
Write-Host "[postgres-restore-drill] backup dir: $backupDir"
Write-Host "[postgres-restore-drill] output: $OutputPath"

if ([string]::IsNullOrWhiteSpace($BackupPath)) {
  Write-Host "[postgres-restore-drill] creating pg_dump backup from source database"
  $env:DATABASE_URL = $SourceDatabaseUrl
  $env:BACKUPS_DIR = $backupDir
@'
from __future__ import annotations

import json
import os
from pathlib import Path

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import AdminBackupRequest

result = get_app_container().maintenance_service.create_backup(AdminBackupRequest(label="postgres-restore-drill"))
Path(os.environ["IMOEX_RESTORE_BACKUP_RESULT"]).write_text(
    json.dumps(result.model_dump(mode="json"), indent=2),
    encoding="utf-8",
)
print(result.backup_path)
'@ | & $python -
  Assert-NativeSuccess "postgres backup creation"
  $backupResult = Get-Content -Path $backupResultPath -Raw | ConvertFrom-Json
  $BackupPath = [string]$backupResult.backup_path
}

if (-not (Test-Path $BackupPath)) {
  throw "Backup artifact does not exist: $BackupPath"
}

$env:IMOEX_RESTORE_BACKUP_PATH = $BackupPath

Write-Host "[postgres-restore-drill] restoring backup into target database"
@'
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url

backup_path = Path(os.environ["IMOEX_RESTORE_BACKUP_PATH"])
target_url = make_url(os.environ["IMOEX_RESTORE_TARGET_DATABASE_URL"])
if not target_url.database:
    raise SystemExit("RestoredDatabaseUrl must include a database name.")

command = [
    os.environ.get("POSTGRES_PG_RESTORE_PATH", "pg_restore"),
    "--clean",
    "--if-exists",
    "--no-owner",
    "--no-privileges",
    "--dbname",
    target_url.database,
]
if target_url.host:
    command.extend(["--host", target_url.host])
if target_url.port:
    command.extend(["--port", str(target_url.port)])
if target_url.username:
    command.extend(["--username", target_url.username])
command.append(str(backup_path))

env = os.environ.copy()
if target_url.password:
    env["PGPASSWORD"] = target_url.password

completed = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
if completed.returncode != 0:
    raise SystemExit((completed.stderr or completed.stdout or "").strip())
'@ | & $python -
Assert-NativeSuccess "postgres restore"

Write-Host "[postgres-restore-drill] validating restored application surfaces"
$env:DATABASE_URL = $RestoredDatabaseUrl
$env:BACKUPS_DIR = Join-Path $drillRoot "restored-backups-$runId"
@'
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.main import app
from libs.utils.config import settings
from libs.utils.db import get_engine

root = os.environ.get("IMOEX_RESTORE_ROOT", "Si")
output_path = Path(os.environ["IMOEX_RESTORE_OUTPUT"])
backup_path = Path(os.environ["IMOEX_RESTORE_BACKUP_PATH"])

with get_engine().connect() as conn:
    final_signals = int(conn.execute(text("SELECT COUNT(*) FROM final_signal")).scalar_one())
    roots = int(conn.execute(text("SELECT COUNT(*) FROM root_series")).scalar_one())

headers = {}
admin_key = os.environ.get("ADMIN_API_KEY")
if admin_key:
    headers[settings.admin_api_key_header] = admin_key

with TestClient(app) as client:
    readiness = client.get("/api/v1/health/product-readiness", params={"root": root})
    readiness.raise_for_status()
    readiness_payload = readiness.json()

    admin_health = client.get("/api/v1/admin/health", headers=headers)
    admin_health.raise_for_status()
    admin_payload = admin_health.json()

assert final_signals > 0, final_signals
assert roots > 0, roots
assert readiness_payload["release_gate"] == "pass", readiness_payload
assert admin_payload["database_status"] == "ok", admin_payload

summary = {
    "generated_at": datetime.now(UTC).isoformat(),
    "root": root,
    "backup_path": str(backup_path),
    "target_database": "postgres",
    "roots": roots,
    "final_signals": final_signals,
    "release_gate": readiness_payload["release_gate"],
    "admin_status": admin_payload["status"],
}
output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
'@ | & $python -
Assert-NativeSuccess "postgres restored validation"

Write-Host "[postgres-restore-drill] OK"
