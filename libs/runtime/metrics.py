from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock

from libs.domain.contracts import RuntimeMetric
from libs.runtime.contracts import RuntimeMetricsSnapshot


class RuntimeMetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def record_request(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        route_key = f"{method.upper()} {path}"
        status_key = f"{status_code}"
        with self._lock:
            self._requests_total += 1
            self._errors_total += 1 if status_code >= 500 else 0
            self._duration_total_ms += float(duration_ms)
            self._duration_max_ms = max(self._duration_max_ms, float(duration_ms))
            self._route_hits[route_key] += 1
            self._status_counts[status_key] += 1

    def snapshot(self) -> RuntimeMetricsSnapshot:
        with self._lock:
            requests_total = self._requests_total
            errors_total = self._errors_total
            duration_total_ms = self._duration_total_ms
            duration_max_ms = self._duration_max_ms
            route_hits = dict(self._route_hits)
            status_counts = dict(self._status_counts)

        avg_duration = (duration_total_ms / requests_total) if requests_total else 0.0
        metrics = [
            RuntimeMetric(
                name="http_requests_total",
                value=float(requests_total),
                unit="count",
                status="ok",
                detail="Total HTTP requests observed by API middleware.",
            ),
            RuntimeMetric(
                name="http_request_errors_total",
                value=float(errors_total),
                unit="count",
                status="ok" if errors_total == 0 else "degraded",
                detail="Total HTTP requests completed with 5xx status.",
            ),
            RuntimeMetric(
                name="http_request_duration_avg_ms",
                value=round(avg_duration, 6),
                unit="ms",
                status="ok",
                detail="Average request duration observed by API middleware.",
            ),
            RuntimeMetric(
                name="http_request_duration_max_ms",
                value=round(duration_max_ms, 6),
                unit="ms",
                status="ok",
                detail="Maximum request duration observed by API middleware.",
            ),
            RuntimeMetric(
                name="http_routes_seen",
                value=float(len(route_hits)),
                unit="count",
                status="ok",
                detail="Distinct method/path combinations observed by API middleware.",
            ),
        ]
        return RuntimeMetricsSnapshot(
            generated_at=datetime.now(UTC),
            metrics=metrics,
            route_hits=route_hits,
            status_counts=status_counts,
        )

    def reset(self) -> None:
        with self._lock:
            self._requests_total = 0
            self._errors_total = 0
            self._duration_total_ms = 0.0
            self._duration_max_ms = 0.0
            self._route_hits: Counter[str] = Counter()
            self._status_counts: Counter[str] = Counter()


@lru_cache(maxsize=1)
def get_runtime_metrics_registry() -> RuntimeMetricsRegistry:
    return RuntimeMetricsRegistry()
