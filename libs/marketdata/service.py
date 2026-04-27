from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

from libs.adapters.contracts import Bar
from libs.adapters.finam import FinamAdapter
from libs.utils.config import Settings, settings

MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")


class LiveQuoteSnapshot(BaseModel):
    provider: str
    root_code: str
    contract: str
    unit: str | None = None
    current_price: float
    price_change_abs: float | None = None
    price_change_pct: float | None = None
    as_of: datetime
    status: str = "fresh"
    detail: str | None = None


class LiveInstrumentMarketSnapshot(BaseModel):
    provider: str
    root_code: str
    contract: str
    unit: str | None = None
    as_of: datetime
    status: str = "fresh"
    detail: str | None = None
    quote: LiveQuoteSnapshot
    daily_bars: list[Bar] = Field(default_factory=list)
    weekly_bars: list[Bar] = Field(default_factory=list)
    monthly_bars: list[Bar] = Field(default_factory=list)


class MarketDataService:
    def __init__(
        self,
        *,
        app_settings: Settings | None = None,
        moex_client: httpx.Client | None = None,
        finam_client: httpx.Client | None = None,
        finam_adapter: FinamAdapter | None = None,
    ) -> None:
        self.settings = app_settings or settings
        self._moex_client = moex_client or httpx.Client(
            base_url=self.settings.moex_iss_base_url.rstrip("/"),
            timeout=self.settings.market_data_http_timeout_seconds,
        )
        self._finam_client = finam_client or httpx.Client(
            base_url="https://api.finam.ru",
            timeout=self.settings.market_data_http_timeout_seconds,
        )
        self._finam_adapter = finam_adapter or FinamAdapter(self.settings)
        self._quote_cache: dict[str, tuple[datetime, LiveQuoteSnapshot]] = {}
        self._snapshot_cache: dict[str, tuple[datetime, LiveInstrumentMarketSnapshot]] = {}
        self._provider_failure_cache: dict[str, tuple[datetime, str]] = {}
        self._finam_jwt_token: str | None = self.settings.finam_jwt_token

    def get_quote_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        providers: list[str],
        unit_hint: str | None = None,
        now: datetime | None = None,
    ) -> LiveQuoteSnapshot | None:
        if not self.settings.market_data_live_enabled:
            return None

        current_time = self._coerce_utc(now or datetime.now(UTC))
        cache_key = f"{root_code}:{contract}:{','.join(_dedupe_preserve_order(providers))}:quote"
        cached = self._quote_cache.get(cache_key)
        if cached is not None and current_time - cached[0] <= timedelta(seconds=self.settings.market_data_cache_ttl_seconds):
            return cached[1].model_copy(deep=True)

        for provider in _provider_order(providers):
            if self._provider_failure_is_fresh(provider, current_time):
                continue
            try:
                snapshot = None
                if provider == "moex":
                    snapshot = self._fetch_moex_quote(root_code=root_code, contract=contract, unit_hint=unit_hint)
                elif provider == "finam":
                    snapshot = self._fetch_finam_quote(root_code=root_code, contract=contract, unit_hint=unit_hint)
                if snapshot is not None:
                    self._provider_failure_cache.pop(provider, None)
                    self._quote_cache[cache_key] = (current_time, snapshot)
                    return snapshot.model_copy(deep=True)
            except (httpx.HTTPError, ValueError) as exc:
                self._record_provider_failure(provider, current_time, exc)
                continue
        return None

    def get_market_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        providers: list[str],
        unit_hint: str | None = None,
        now: datetime | None = None,
    ) -> LiveInstrumentMarketSnapshot | None:
        if not self.settings.market_data_live_enabled:
            return None

        current_time = self._coerce_utc(now or datetime.now(UTC))
        cache_key = f"{root_code}:{contract}:{','.join(_dedupe_preserve_order(providers))}:full"
        cached = self._snapshot_cache.get(cache_key)
        if cached is not None and current_time - cached[0] <= timedelta(seconds=self.settings.market_data_cache_ttl_seconds):
            return cached[1].model_copy(deep=True)

        for provider in _provider_order(providers):
            if self._provider_failure_is_fresh(provider, current_time):
                continue
            try:
                snapshot = None
                if provider == "moex":
                    snapshot = self._fetch_moex_snapshot(root_code=root_code, contract=contract, unit_hint=unit_hint, now=current_time)
                elif provider == "finam":
                    snapshot = self._fetch_finam_snapshot(root_code=root_code, contract=contract, unit_hint=unit_hint, now=current_time)
                if snapshot is not None:
                    self._provider_failure_cache.pop(provider, None)
                    self._snapshot_cache[cache_key] = (current_time, snapshot)
                    return snapshot.model_copy(deep=True)
            except (httpx.HTTPError, ValueError) as exc:
                self._record_provider_failure(provider, current_time, exc)
                continue
        return None

    def _provider_failure_is_fresh(self, provider: str, current_time: datetime) -> bool:
        cached = self._provider_failure_cache.get(provider)
        if cached is None:
            return False
        failed_at, _detail = cached
        return current_time - failed_at <= timedelta(seconds=self.settings.market_data_cache_ttl_seconds)

    def _record_provider_failure(self, provider: str, failed_at: datetime, exc: Exception) -> None:
        self._provider_failure_cache[provider] = (failed_at, f"{type(exc).__name__}: {exc}")

    def _fetch_moex_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        unit_hint: str | None,
        now: datetime,
    ) -> LiveInstrumentMarketSnapshot | None:
        quote = self._fetch_moex_quote(root_code=root_code, contract=contract, unit_hint=unit_hint)
        if quote is None:
            return None

        daily_bars = self._fetch_moex_candles(
            root_code=root_code,
            contract=contract,
            timeframe="1D",
            interval=10,
            from_at=now - timedelta(hours=8),
            till_at=now,
        )
        weekly_bars = self._fetch_moex_candles(
            root_code=root_code,
            contract=contract,
            timeframe="1W",
            interval=24,
            from_at=now - timedelta(days=8),
            till_at=now,
        )
        monthly_bars = self._fetch_moex_candles(
            root_code=root_code,
            contract=contract,
            timeframe="1M",
            interval=24,
            from_at=now - timedelta(days=40),
            till_at=now,
        )
        return LiveInstrumentMarketSnapshot(
            provider="moex",
            root_code=root_code,
            contract=contract,
            unit=quote.unit,
            as_of=quote.as_of,
            status="fresh",
            detail="Live quote and candles from MOEX ISS.",
            quote=quote,
            daily_bars=daily_bars,
            weekly_bars=weekly_bars,
            monthly_bars=monthly_bars,
        )

    def _fetch_moex_quote(
        self,
        *,
        root_code: str,
        contract: str,
        unit_hint: str | None,
    ) -> LiveQuoteSnapshot | None:
        response = self._moex_client.get(
            f"/engines/futures/markets/forts/securities/{contract}.json",
            params={
                "iss.meta": "off",
                "iss.only": "marketdata,securities",
                "lang": "en",
            },
        )
        response.raise_for_status()
        payload = response.json()
        market_rows = _extract_iss_rows(payload, "marketdata")
        security_rows = _extract_iss_rows(payload, "securities")
        row = market_rows[0] if market_rows else {}
        security_row = security_rows[0] if security_rows else {}

        current_price = _first_float(
            row,
            [
                "LAST",
                "LCURRENTPRICE",
                "MARKETPRICE",
                "MARKETPRICE2",
                "SETTLEPRICE",
                "SETTLEPRC",
                "OPENPERIODPRICE",
            ],
        )
        if current_price is None:
            return None

        previous_price = _first_float(
            row,
            [
                "PREVSETTLEPRICE",
                "PREVPRICE",
                "LCLOSEPRICE",
                "SETTLEPRICE",
                "PREVWAPRICE",
            ],
        )
        change_abs: float | None = None
        change_pct: float | None = None
        if previous_price is not None and previous_price > 0:
            change_abs = round(current_price - previous_price, 2)
            change_pct = round(change_abs / previous_price, 4)
        else:
            change_pct_field = _first_float(row, ["LASTTOPREVPRICE", "SETTLETOPREVSETTLEPRC", "CHANGEPRCNT"])
            if change_pct_field is not None:
                change_pct = round(change_pct_field / 100.0, 4)

        as_of = _parse_moex_datetime(row.get("SYSTIME"))
        if as_of is None:
            as_of = _combine_moex_trade_time(
                trade_date=_first_text(row, ["TRADEDATE", "TRADEDATESTRING"]),
                trade_time=_first_text(row, ["TIME", "TRADINGSESSION", "UPDATETIME"]),
            ) or datetime.now(UTC)

        unit = _first_text(security_row, ["FACEUNIT", "CURRENCYID"]) or unit_hint
        return LiveQuoteSnapshot(
            provider="moex",
            root_code=root_code,
            contract=contract,
            unit=unit,
            current_price=round(current_price, 2),
            price_change_abs=change_abs,
            price_change_pct=change_pct,
            as_of=self._coerce_utc(as_of),
            status="fresh",
            detail="Live quote from MOEX ISS marketdata.",
        )

    def _fetch_moex_candles(
        self,
        *,
        root_code: str,
        contract: str,
        timeframe: str,
        interval: int,
        from_at: datetime,
        till_at: datetime,
    ) -> list[Bar]:
        response = self._moex_client.get(
            f"/engines/futures/markets/forts/securities/{contract}/candles.json",
            params={
                "iss.meta": "off",
                "iss.only": "candles",
                "from": self._format_moex_datetime(from_at),
                "till": self._format_moex_datetime(till_at),
                "interval": interval,
                "lang": "en",
            },
        )
        response.raise_for_status()
        rows = _extract_iss_rows(response.json(), "candles")
        bars: list[Bar] = []
        for row in rows:
            open_price = _first_float(row, ["open", "OPEN"])
            high_price = _first_float(row, ["high", "HIGH"])
            low_price = _first_float(row, ["low", "LOW"])
            close_price = _first_float(row, ["close", "CLOSE"])
            begin = _parse_moex_datetime(row.get("begin") or row.get("BEGIN"))
            end = _parse_moex_datetime(row.get("end") or row.get("END")) or begin
            if None in {open_price, high_price, low_price, close_price} or begin is None or end is None:
                continue
            volume = _first_float(row, ["volume", "VOLUME", "value", "VALUE"]) or 0.0
            bars.append(
                Bar(
                    provider="moex",
                    root=root_code,
                    contract=contract,
                    timeframe=timeframe,
                    open=round(open_price, 2),
                    high=round(high_price, 2),
                    low=round(low_price, 2),
                    close=round(close_price, 2),
                    volume=float(volume),
                    start_at=self._coerce_utc(begin),
                    end_at=self._coerce_utc(end),
                )
            )
        return bars

    def _fetch_finam_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        unit_hint: str | None,
        now: datetime,
    ) -> LiveInstrumentMarketSnapshot | None:
        quote = self._fetch_finam_quote(root_code=root_code, contract=contract, unit_hint=unit_hint)
        if quote is None:
            return None
        symbol = self._finam_symbol(root_code=root_code, contract=contract)
        if symbol is None:
            return None
        daily_bars = self._fetch_finam_bars(symbol=symbol, root_code=root_code, contract=contract, timeframe="1D", timeframe_code="TIME_FRAME_M30", start_at=now - timedelta(days=1), end_at=now)
        weekly_bars = self._fetch_finam_bars(symbol=symbol, root_code=root_code, contract=contract, timeframe="1W", timeframe_code="TIME_FRAME_D1", start_at=now - timedelta(days=8), end_at=now)
        monthly_bars = self._fetch_finam_bars(symbol=symbol, root_code=root_code, contract=contract, timeframe="1M", timeframe_code="TIME_FRAME_D1", start_at=now - timedelta(days=40), end_at=now)
        return LiveInstrumentMarketSnapshot(
            provider="finam",
            root_code=root_code,
            contract=contract,
            unit=quote.unit,
            as_of=quote.as_of,
            status="fresh",
            detail="Live quote and bars from Finam Trade API.",
            quote=quote,
            daily_bars=daily_bars,
            weekly_bars=weekly_bars,
            monthly_bars=monthly_bars,
        )

    def _fetch_finam_quote(
        self,
        *,
        root_code: str,
        contract: str,
        unit_hint: str | None,
    ) -> LiveQuoteSnapshot | None:
        symbol = self._finam_symbol(root_code=root_code, contract=contract)
        headers = self._finam_auth_headers()
        if symbol is None or not headers:
            return None
        response = self._finam_client.get(f"/v1/instruments/{symbol}/quotes/latest", headers=headers)
        response.raise_for_status()
        payload = response.json()
        price = _deep_first_float(payload, ["last", "price", "value", "close", "current_price"])
        if price is None:
            return None
        change_abs = _deep_first_float(payload, ["change_abs", "absolute_change", "delta"])
        change_pct = _deep_first_float(payload, ["change_percent", "percent_change", "relative_change"])
        if change_pct is not None and abs(change_pct) > 1:
            change_pct = change_pct / 100.0
        as_of = _deep_first_datetime(payload, ["timestamp", "time", "as_of"]) or datetime.now(UTC)
        return LiveQuoteSnapshot(
            provider="finam",
            root_code=root_code,
            contract=contract,
            unit=unit_hint,
            current_price=round(price, 2),
            price_change_abs=round(change_abs, 2) if change_abs is not None else None,
            price_change_pct=round(change_pct, 4) if change_pct is not None else None,
            as_of=self._coerce_utc(as_of),
            status="fresh",
            detail="Live quote from Finam Trade API.",
        )

    def _fetch_finam_bars(
        self,
        *,
        symbol: str,
        root_code: str,
        contract: str,
        timeframe: str,
        timeframe_code: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[Bar]:
        headers = self._finam_auth_headers()
        if not headers:
            return []
        response = self._finam_client.get(
            f"/v1/instruments/{symbol}/bars",
            headers=headers,
            params={
                "timeframe": timeframe_code,
                "interval.start_time": self._format_finam_datetime(start_at),
                "interval.end_time": self._format_finam_datetime(end_at),
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_bars = payload.get("bars") if isinstance(payload, dict) else None
        if not isinstance(raw_bars, list):
            return []
        bars: list[Bar] = []
        for item in raw_bars:
            if not isinstance(item, dict):
                continue
            open_price = _deep_first_float(item, ["open", "price", "value"])
            high_price = _deep_first_float(item, ["high", "price", "value"])
            low_price = _deep_first_float(item, ["low", "price", "value"])
            close_price = _deep_first_float(item, ["close", "price", "value"])
            begin = _deep_first_datetime(item, ["timestamp", "time", "begin", "start_time"])
            end = _deep_first_datetime(item, ["end", "end_time", "close_time"]) or begin
            if None in {open_price, high_price, low_price, close_price} or begin is None or end is None:
                continue
            volume = _deep_first_float(item, ["volume", "value"]) or 0.0
            bars.append(
                Bar(
                    provider="finam",
                    root=root_code,
                    contract=contract,
                    timeframe=timeframe,
                    open=round(open_price, 2),
                    high=round(high_price, 2),
                    low=round(low_price, 2),
                    close=round(close_price, 2),
                    volume=volume,
                    start_at=self._coerce_utc(begin),
                    end_at=self._coerce_utc(end),
                )
            )
        return bars

    def _finam_symbol(self, *, root_code: str, contract: str) -> str | None:
        return self._finam_adapter.resolve_symbol(contract) or self._finam_adapter.resolve_symbol(root_code)

    def _finam_auth_headers(self) -> dict[str, str]:
        token = self._finam_jwt_token
        if token is None and self.settings.finam_secret_token:
            response = self._finam_client.post("/v1/sessions", json={"secret": self.settings.finam_secret_token})
            response.raise_for_status()
            payload = response.json()
            token = payload.get("token") if isinstance(payload, dict) else None
            if isinstance(token, str) and token:
                self._finam_jwt_token = token
        if self._finam_jwt_token:
            return {"Authorization": f"Bearer {self._finam_jwt_token}"}
        return {}

    def _format_moex_datetime(self, value: datetime) -> str:
        localized = self._coerce_utc(value).astimezone(MOSCOW_TIMEZONE)
        return localized.strftime("%Y-%m-%d %H:%M:%S")

    def _format_finam_datetime(self, value: datetime) -> str:
        return self._coerce_utc(value).isoformat().replace("+00:00", "Z")

    def _coerce_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


@lru_cache(maxsize=1)
def get_market_data_service() -> MarketDataService:
    return MarketDataService()


def _provider_order(providers: list[str]) -> list[str]:
    ordered = _dedupe_preserve_order(providers)
    if "moex" not in ordered:
        ordered.append("moex")
    if "finam" not in ordered:
        ordered.append("finam")
    return ordered


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.lower().strip()
        if normalized in seen or not normalized:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _extract_iss_rows(payload: dict[str, Any], block_name: str) -> list[dict[str, Any]]:
    block = payload.get(block_name)
    if not isinstance(block, dict):
        return []
    columns = block.get("columns")
    data = block.get("data")
    if not isinstance(columns, list) or not isinstance(data, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, list):
            rows.append(dict(zip(columns, item, strict=False)))
    return rows


def _first_text(mapping: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value in (None, ""):
            continue
        return str(value)
    return None


def _first_float(mapping: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = mapping.get(key)
        converted = _to_float(value)
        if converted is not None:
            return converted
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        nested = _deep_first_float(value, ["value"])
        if nested is not None:
            return nested
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_moex_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=MOSCOW_TIMEZONE).astimezone(UTC)
    text = str(value).strip()
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=MOSCOW_TIMEZONE).astimezone(UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None


def _combine_moex_trade_time(*, trade_date: str | None, trade_time: str | None) -> datetime | None:
    if not trade_date or not trade_time:
        return None
    try:
        return datetime.fromisoformat(f"{trade_date}T{trade_time}").replace(tzinfo=MOSCOW_TIMEZONE).astimezone(UTC)
    except ValueError:
        return None


def _deep_first_float(payload: Any, preferred_keys: list[str]) -> float | None:
    if isinstance(payload, dict):
        for key in preferred_keys:
            if key in payload:
                direct = _to_float(payload[key])
                if direct is not None:
                    return direct
        for value in payload.values():
            nested = _deep_first_float(value, preferred_keys)
            if nested is not None:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _deep_first_float(item, preferred_keys)
            if nested is not None:
                return nested
    return None


def _deep_first_datetime(payload: Any, preferred_keys: list[str]) -> datetime | None:
    if isinstance(payload, dict):
        for key in preferred_keys:
            if key in payload:
                direct = _parse_generic_datetime(payload[key])
                if direct is not None:
                    return direct
        for value in payload.values():
            nested = _deep_first_datetime(value, preferred_keys)
            if nested is not None:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _deep_first_datetime(item, preferred_keys)
            if nested is not None:
                return nested
    return None


def _parse_generic_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None
