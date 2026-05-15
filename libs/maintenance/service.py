from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from libs.domain.contracts import (
    AdminBackupRequest,
    AdminBackupResult,
    AdminCleanupRequest,
    AdminCleanupResult,
)
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.quality.repository import SqlAlchemySourceQualityRepository
from libs.utils.config import settings
from libs.utils.db import ensure_schema


@dataclass
class BackupInventory:
    backup_dir: str
    artifacts: int
    total_size_bytes: int
    latest_backup_at: datetime | None = None


class MaintenanceService:
    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        quality_repository: SqlAlchemySourceQualityRepository,
    ) -> None:
        self.repository = repository
        self.quality_repository = quality_repository

    def create_backup(self, payload: AdminBackupRequest) -> AdminBackupResult:
        backup_dir = self._resolve_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        database_kind = self._database_kind(settings.database_url)
        created_at = datetime.now(UTC)
        label_suffix = f"-{self._sanitize_label(payload.label)}" if payload.label else ""

        if database_kind == "sqlite":
            ensure_schema()
            source_path = self._resolve_sqlite_path()
            target_path = backup_dir / f"imoex-backup-{created_at:%Y%m%d-%H%M%S}{label_suffix}.sqlite3"
            with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
                source.backup(target)
            backup_format = "sqlite3"
            restore_hint = "Restore by copying this sqlite3 artifact to a fresh DATABASE_URL path."
        elif database_kind == "postgresql":
            target_path = backup_dir / f"imoex-backup-{created_at:%Y%m%d-%H%M%S}{label_suffix}.pg.dump"
            self._create_postgres_backup(target_path)
            backup_format = "pg_dump_custom"
            restore_hint = "Restore with scripts/postgres_restore_drill.ps1 or pg_restore --format=custom."
        else:
            raise ValueError(f"Backup is not supported for database kind: {database_kind}.")

        return AdminBackupResult(
            backup_path=str(target_path),
            created_at=created_at,
            size_bytes=int(target_path.stat().st_size),
            database_kind=database_kind,
            backup_format=backup_format,
            restore_hint=restore_hint,
        )

    def cleanup(self, payload: AdminCleanupRequest) -> AdminCleanupResult:
        deleted = self.repository.purge_operational_data_older_than(days=payload.retention_days)
        deleted["quality_checks"] = self.quality_repository.purge_older_than(days=payload.retention_days)
        details = [f"{name}={count}" for name, count in deleted.items() if count > 0]
        return AdminCleanupResult(
            retention_days=payload.retention_days,
            total_deleted=sum(deleted.values()),
            details=details,
        )

    def backup_inventory(self) -> BackupInventory:
        backup_dir = self._resolve_backup_dir()
        if not backup_dir.exists():
            return BackupInventory(
                backup_dir=str(backup_dir),
                artifacts=0,
                total_size_bytes=0,
                latest_backup_at=None,
            )

        files = sorted(
            (
                item
                for pattern in ("*.sqlite3", "*.pg.dump")
                for item in backup_dir.glob(pattern)
                if item.is_file()
            ),
            key=lambda item: item.stat().st_mtime,
        )
        if not files:
            return BackupInventory(
                backup_dir=str(backup_dir),
                artifacts=0,
                total_size_bytes=0,
                latest_backup_at=None,
            )

        latest_file = files[-1]
        latest_backup_at = datetime.fromtimestamp(latest_file.stat().st_mtime, tz=UTC)
        total_size_bytes = sum(int(item.stat().st_size) for item in files)
        return BackupInventory(
            backup_dir=str(backup_dir),
            artifacts=len(files),
            total_size_bytes=total_size_bytes,
            latest_backup_at=latest_backup_at,
        )

    def _resolve_backup_dir(self) -> Path:
        backup_dir = Path(settings.backups_dir)
        if not backup_dir.is_absolute():
            backup_dir = Path.cwd() / backup_dir
        return backup_dir.resolve()

    def _resolve_sqlite_path(self) -> Path:
        database_url = settings.database_url
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Backup is currently supported only for sqlite databases.")

        raw_path = database_url.removeprefix("sqlite:///")
        path = Path(raw_path)
        if str(path) == ":memory:":
            raise ValueError("Backup is not supported for in-memory sqlite databases.")
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def _create_postgres_backup(self, target_path: Path) -> None:
        url = make_url(settings.database_url)
        if not url.database:
            raise ValueError("Postgres backup requires a database name in DATABASE_URL.")

        command = [
            settings.postgres_pg_dump_path,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(target_path),
        ]
        if url.host:
            command.extend(["--host", url.host])
        if url.port:
            command.extend(["--port", str(url.port)])
        if url.username:
            command.extend(["--username", url.username])
        command.append(url.database)

        env = None
        if url.password:
            env = os.environ.copy()
            env["PGPASSWORD"] = url.password

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "Postgres backup requires pg_dump on PATH or POSTGRES_PG_DUMP_PATH."
            ) from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"pg_dump failed with exit code {completed.returncode}: {detail}")
        if not target_path.exists() or target_path.stat().st_size <= 0:
            raise RuntimeError("pg_dump completed but did not create a non-empty backup artifact.")

    def _database_kind(self, database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return "sqlite"
        drivername = make_url(database_url).drivername.lower()
        if drivername.startswith("postgresql") or drivername.startswith("postgres"):
            return "postgresql"
        return drivername.split("+", maxsplit=1)[0]

    def _sanitize_label(self, value: str) -> str:
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
        while "--" in safe:
            safe = safe.replace("--", "-")
        return safe.strip("-") or "manual"
