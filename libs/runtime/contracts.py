from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from libs.domain.contracts import RuntimeMetric


class FeatureFlagState(BaseModel):
    name: str
    enabled: bool
    source: str = "settings"
    detail: str | None = None


class RuntimeMetricsSnapshot(BaseModel):
    generated_at: datetime
    metrics: list[RuntimeMetric] = Field(default_factory=list)
    route_hits: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
