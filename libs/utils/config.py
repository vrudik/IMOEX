from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_state_root() -> Path:
    candidates = []
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "imoex-trading-system")
    candidates.append(Path(tempfile.gettempdir()) / "imoex-trading-system")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue

    return Path(tempfile.gettempdir()) / "imoex-trading-system"


def _default_database_url() -> str:
    return f"sqlite:///{(_default_state_root() / 'local.db').as_posix()}"


def _default_backups_dir() -> str:
    return (_default_state_root() / "backups").as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = _default_database_url()
    backups_dir: str = _default_backups_dir()
    tbank_token: str | None = None
    tbank_account_id: str | None = None
    tbank_use_sandbox: bool = True
    tbank_app_name: str = "imoex-signals"
    tbank_symbol_map_json: str = "{}"
    alor_refresh_token: str | None = None
    alor_access_token: str | None = None
    alor_portfolio: str | None = None
    alor_use_test_env: bool = True
    alor_symbol_map_json: str = "{}"
    finam_secret_token: str | None = None
    finam_jwt_token: str | None = None
    finam_account_id: str | None = None
    finam_use_demo: bool = False
    finam_symbol_map_json: str = "{}"
    bcs_api_token: str | None = None
    bcs_client_id: str | None = None
    bcs_market_data_ws_url: str = "wss://trade-api.bcs.ru/websocket/market-data"
    bcs_order_book_ws_url: str = "wss://trade-api.bcs.ru/websocket/market-data/order-book"
    bcs_limits_ws_url: str = "wss://trade-api.bcs.ru/websocket/limits"
    bcs_symbol_map_json: str = "{}"
    moex_iss_base_url: str = "https://iss.moex.com/iss"
    moex_iss_timeout_seconds: float = 10.0
    moex_iss_securities_path: str = "/engines/futures/markets/forts/securities.json"
    moex_iss_calendar_path: str = "/history/engines/futures/markets/forts/dates.json"
    market_data_live_enabled: bool = True
    market_data_http_timeout_seconds: float = 2.5
    market_data_cache_ttl_seconds: int = 45
    moex_reference_auto_sync_enabled: bool = True
    moex_reference_auto_sync_interval_hours: int = 12
    moex_reference_retry_cooldown_minutes: int = 30
    moex_reference_calendar_lookback_days: int = 7
    moex_reference_calendar_lookahead_days: int = 14
    log_level: str = "INFO"
    log_json: bool = True
    feature_flags_json: str = "{}"
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Moscow"
    scheduler_jobs_json: str = "[]"
    scheduler_poll_interval_seconds: float = 30.0
    scheduler_leader_lease_seconds: int = 90
    scheduler_leader_lock_key: str = "scheduler:leader"
    scheduler_alert_stale_after_minutes: int = 10
    scheduler_alert_failed_runs_limit: int = 5
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_enabled: bool = False
    telegram_parse_mode: str = "HTML"
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_disable_link_preview: bool = True

    @property
    def tbank_symbol_map(self) -> dict[str, str]:
        try:
            loaded = json.loads(self.tbank_symbol_map_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items()}

    @property
    def alor_symbol_map(self) -> dict[str, str]:
        try:
            loaded = json.loads(self.alor_symbol_map_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items()}

    @property
    def finam_symbol_map(self) -> dict[str, str]:
        try:
            loaded = json.loads(self.finam_symbol_map_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items()}

    @property
    def bcs_symbol_map(self) -> dict[str, str]:
        try:
            loaded = json.loads(self.bcs_symbol_map_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items()}

    @property
    def feature_flags(self) -> dict[str, bool]:
        try:
            loaded = json.loads(self.feature_flags_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): bool(value) for key, value in loaded.items()}

    @property
    def scheduler_jobs(self) -> list[dict[str, object]]:
        try:
            loaded = json.loads(self.scheduler_jobs_json)
        except json.JSONDecodeError:
            return []
        if not isinstance(loaded, list):
            return []
        normalized: list[dict[str, object]] = []
        for item in loaded:
            if isinstance(item, dict):
                normalized.append({str(key): value for key, value in item.items()})
        return normalized


settings = Settings()

