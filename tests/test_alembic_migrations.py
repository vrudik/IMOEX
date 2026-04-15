from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_bootstraps_current_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "alembic.db"
    config = Config("alembic.ini")
    config.set_main_option("script_location", str((Path.cwd() / "alembic").resolve()))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}", future=True)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "root_series" in tables
    assert "contract_meta" in tables
    assert "trading_session" in tables
    assert "final_signal" in tables
    assert "signal_resolution" in tables
    assert "user_journal_entry" in tables
    assert "user_notification_preference" in tables
    assert "notification_delivery_event" in tables
    assert "scheduler_run" in tables
    assert "scheduler_lock" in tables

    version_rows = engine.connect().exec_driver_sql("SELECT version_num FROM alembic_version").fetchall()
    assert version_rows == [("20260409_06",)]
