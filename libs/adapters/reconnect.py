from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel


class ReconnectPolicy(BaseModel):
    max_retries: int = 8
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    multiplier: float = 2.0


class ReconnectState(BaseModel):
    connected: bool
    reconnect_attempts: int
    next_retry_seconds: float | None = None
    last_disconnect_at: datetime | None = None
    status: str
    detail: str


class ReconnectManager:
    def __init__(self, policy: ReconnectPolicy | None = None) -> None:
        self.policy = policy or ReconnectPolicy()
        self._connected = True
        self._reconnect_attempts = 0
        self._last_disconnect_at: datetime | None = None
        self._detail = "stream connected"

    def record_disconnect(self, detail: str) -> ReconnectState:
        self._connected = False
        self._reconnect_attempts = min(self._reconnect_attempts + 1, self.policy.max_retries)
        self._last_disconnect_at = datetime.now(UTC)
        self._detail = detail
        return self.snapshot()

    def record_reconnect(self, detail: str = "stream connected") -> ReconnectState:
        self._connected = True
        self._reconnect_attempts = 0
        self._detail = detail
        return self.snapshot()

    def snapshot(self) -> ReconnectState:
        next_retry_seconds = None
        status = "ok"
        if not self._connected:
            exponent = max(0, self._reconnect_attempts - 1)
            next_retry_seconds = min(
                self.policy.max_delay_seconds,
                self.policy.base_delay_seconds * (self.policy.multiplier**exponent),
            )
            status = "degraded"
        return ReconnectState(
            connected=self._connected,
            reconnect_attempts=self._reconnect_attempts,
            next_retry_seconds=next_retry_seconds,
            last_disconnect_at=self._last_disconnect_at,
            status=status,
            detail=self._detail,
        )
