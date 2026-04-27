from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from libs.domain.contracts import AdminBackupRequest
from libs.maintenance.service import MaintenanceService
from libs.utils.config import settings


def test_postgres_backup_uses_pg_dump_without_password_in_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run(command, *, check, capture_output, text, env):
        calls.append((list(command), env))
        target_path = Path(command[command.index("--file") + 1])
        target_path.write_bytes(b"PGDMP fixture")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://imoex:secret@localhost:5432/imoex_prod")
    monkeypatch.setattr(settings, "backups_dir", tmp_path.as_posix())
    monkeypatch.setattr(settings, "postgres_pg_dump_path", "pg_dump")
    monkeypatch.setattr("libs.maintenance.service.subprocess.run", fake_run)

    result = MaintenanceService(None, None).create_backup(AdminBackupRequest(label="prod smoke"))

    assert result.database_kind == "postgresql"
    assert result.backup_format == "pg_dump_custom"
    assert result.backup_path.endswith("-prod-smoke.pg.dump")
    assert result.size_bytes > 0
    assert "postgres_restore_drill.ps1" in (result.restore_hint or "")
    assert calls
    command, env = calls[0]
    assert "secret" not in command
    assert env is not None
    assert env["PGPASSWORD"] == "secret"
    assert command[:4] == ["pg_dump", "--format=custom", "--no-owner", "--no-privileges"]
    assert "--host" in command and "localhost" in command
    assert "--port" in command and "5432" in command
    assert "--username" in command and "imoex" in command
    assert command[-1] == "imoex_prod"


def test_postgres_backup_reports_missing_pg_dump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("pg_dump")

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://imoex:secret@localhost:5432/imoex_prod")
    monkeypatch.setattr(settings, "backups_dir", tmp_path.as_posix())
    monkeypatch.setattr("libs.maintenance.service.subprocess.run", fake_run)

    with pytest.raises(ValueError, match="pg_dump"):
        MaintenanceService(None, None).create_backup(AdminBackupRequest(label="prod"))


def test_backup_inventory_counts_sqlite_and_postgres_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "imoex-backup-20260424-100000.sqlite3").write_bytes(b"sqlite")
    (tmp_path / "imoex-backup-20260424-100100.pg.dump").write_bytes(b"pgdump")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    monkeypatch.setattr(settings, "backups_dir", tmp_path.as_posix())

    inventory = MaintenanceService(None, None).backup_inventory()

    assert inventory.artifacts == 2
    assert inventory.total_size_bytes == len(b"sqlite") + len(b"pgdump")
    assert inventory.latest_backup_at is not None
