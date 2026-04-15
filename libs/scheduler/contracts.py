from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


_WEEKDAY_MAP = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


class ScheduledJobSpec(BaseModel):
    job_id: str
    command: str
    description: str
    timezone: str
    hour: int
    minute: int
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    enabled: bool = True
    tolerance_minutes: int = 15
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("weekdays", mode="before")
    @classmethod
    def _normalize_weekdays(cls, value: object) -> list[int]:
        if value in (None, ""):
            return [0, 1, 2, 3, 4]
        if not isinstance(value, list):
            raise TypeError("weekdays must be a list")
        normalized: list[int] = []
        for item in value:
            if isinstance(item, str):
                key = item.strip().lower()
                if key not in _WEEKDAY_MAP:
                    raise ValueError(f"Unsupported weekday: {item}")
                normalized.append(_WEEKDAY_MAP[key])
                continue
            normalized.append(int(item))
        result = sorted({max(0, min(6, int(item))) for item in normalized})
        if not result:
            raise ValueError("weekdays must not be empty")
        return result


class ScheduledJobSnapshot(BaseModel):
    job_id: str
    command: str
    description: str
    timezone: str
    enabled: bool
    weekdays: list[int] = Field(default_factory=list)
    hour: int
    minute: int
    tolerance_minutes: int
    payload: dict[str, Any] = Field(default_factory=dict)
    scheduled_for: datetime | None = None
    next_run_at: datetime | None = None
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    last_run_status: str | None = None
    last_run_detail: str | None = None
    due_now: bool = False


class SchedulePlan(BaseModel):
    generated_at: datetime
    as_of: datetime
    timezone: str
    jobs: list[ScheduledJobSnapshot] = Field(default_factory=list)


class SchedulerRunHistoryEntry(BaseModel):
    run_id: str
    job_id: str
    command: str
    trigger_mode: str
    idempotency_key: str
    status: str
    detail: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    scheduled_for: datetime | None = None
    started_at: datetime
    finished_at: datetime | None = None


class SchedulerLeaderSnapshot(BaseModel):
    lock_key: str
    is_leader: bool
    owner_id: str | None = None
    acquired_at: datetime | None = None
    expires_at: datetime | None = None
    lease_seconds: int
    detail: str | None = None


class ScheduleExecutionItem(BaseModel):
    run_id: str | None = None
    trigger_mode: str | None = None
    idempotency_key: str | None = None
    job_id: str
    command: str
    scheduled_for: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    executed: bool
    status: str
    detail: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None


class SchedulerLoopIteration(BaseModel):
    iteration: int
    as_of: datetime
    result: ScheduleExecutionResult


class SchedulerLoopResult(BaseModel):
    started_at: datetime
    finished_at: datetime
    owner_id: str
    iterations_requested: int
    iterations_completed: int
    leader: SchedulerLeaderSnapshot
    dry_run: bool = False
    sleep_seconds: float = 0.0
    iterations: list[SchedulerLoopIteration] = Field(default_factory=list)


class ScheduleExecutionResult(BaseModel):
    generated_at: datetime
    as_of: datetime
    timezone: str
    dry_run: bool = False
    due_jobs: int = 0
    executed_jobs: int = 0
    items: list[ScheduleExecutionItem] = Field(default_factory=list)
