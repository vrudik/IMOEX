from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import httpx

from libs.reference.contracts import MoexContractReference
from libs.utils.config import settings


class MoexIssClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=settings.moex_iss_base_url.rstrip("/"),
            timeout=settings.moex_iss_timeout_seconds,
        )

    def fetch_contracts_payload(self) -> dict[str, Any]:
        response = self._client.get(settings.moex_iss_securities_path)
        response.raise_for_status()
        return response.json()

    def fetch_calendar_payload(self, *, from_date: date | None = None, to_date: date | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if from_date is not None:
            params["from"] = from_date.isoformat()
        if to_date is not None:
            params["till"] = to_date.isoformat()
        response = self._client.get(settings.moex_iss_calendar_path, params=params)
        response.raise_for_status()
        return response.json()

    def parse_contracts(self, payload: dict[str, Any]) -> list[MoexContractReference]:
        rows = _extract_iss_rows(payload, preferred_blocks=("securities", "futures"))
        contracts: list[MoexContractReference] = []
        for row in rows:
            contract_code = str(row.get("SECID") or "").strip()
            if not contract_code:
                continue
            root_code = str(row.get("ASSETCODE") or _extract_root_code(contract_code)).strip()
            expiry_date = _parse_date(
                row.get("MATDATE") or row.get("EXPIRYDATE") or row.get("LASTDELDATE") or row.get("SETTLEDATE")
            )
            last_trade_date = _parse_date(row.get("LASTTRADEDATE") or row.get("LASTDELDATE")) or expiry_date
            if not root_code or expiry_date is None or last_trade_date is None:
                continue
            contracts.append(
                MoexContractReference(
                    contract_code=contract_code,
                    root_code=root_code,
                    expiry_date=expiry_date,
                    last_trade_date=last_trade_date,
                    tick_size=float(row.get("MINSTEP") or 1.0),
                    lot_size=int(row.get("LOTSIZE") or 1),
                    currency=str(row.get("FACEUNIT") or row.get("CURRENCYID") or _default_currency(root_code)),
                    active_flag=bool(row.get("TRADINGSTATUS") != "S"),
                )
            )
        return contracts

    def parse_calendar(self, payload: dict[str, Any]) -> dict[date, tuple[date, bool]]:
        rows = _extract_iss_rows(payload, preferred_blocks=("dates", "calendar"))
        mapping: dict[date, tuple[date, bool]] = {}
        for row in rows:
            calendar_day = _parse_date(row.get("TRADEDATE") or row.get("DATE") or row.get("DAY"))
            trading_day = _parse_date(row.get("TRADINGDAY") or row.get("TRADE_DAY") or row.get("SETTLEDATE"))
            if calendar_day is None:
                continue
            if trading_day is None:
                trading_day = calendar_day
            is_weekend_session = str(row.get("ISWEEKENDSESSION") or row.get("WEEKEND_SESSION") or "0") in {"1", "true", "True"}
            mapping[calendar_day] = (trading_day, is_weekend_session)
        return mapping


def _extract_iss_rows(payload: dict[str, Any], *, preferred_blocks: tuple[str, ...]) -> list[dict[str, Any]]:
    for block_name in preferred_blocks:
        block = payload.get(block_name)
        if not isinstance(block, dict):
            continue
        columns = block.get("columns")
        data = block.get("data")
        if not isinstance(columns, list) or not isinstance(data, list):
            continue
        rows: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, list):
                rows.append(dict(zip(columns, item, strict=False)))
        if rows:
            return rows
    return []


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _extract_root_code(contract_code: str) -> str:
    match = re.match(r"([A-Za-z]+)", contract_code)
    return match.group(1) if match else contract_code


def _default_currency(root_code: str) -> str:
    if root_code.upper() == "SI":
        return "RUB"
    if root_code.upper() == "BR":
        return "USD"
    return "PTS"
