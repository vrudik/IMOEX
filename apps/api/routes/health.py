from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from libs.domain.demo_data import list_sources
from libs.utils.db import database_available

router = APIRouter(tags=["health"])


class BootstrapState(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, BootstrapState]


class SourceHealthResponse(BaseModel):
    provider: str
    role: str
    status: str
    detail: str
    freshness_seconds: int | None = None
    primary: bool = False


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", checks={"app": BootstrapState(status="ok", detail="running")})


@router.get("/health/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    db_ok = database_available()
    checks = {
        "db": BootstrapState(status="ok" if db_ok else "not_ok", detail="reachable" if db_ok else "unreachable"),
    }
    status = "ok" if all(v.status == "ok" for v in checks.values()) else "not_ok"
    return HealthResponse(status=status, checks=checks)


@router.get("/health/sources", response_model=list[SourceHealthResponse])
async def sources() -> list[SourceHealthResponse]:
    db_ok = database_available()
    rows = [SourceHealthResponse.model_validate(item.model_dump()) for item in list_sources()]
    rows.append(
        SourceHealthResponse(
            provider="database",
            role="storage",
            status="ok" if db_ok else "not_ok",
            detail="reachable" if db_ok else "unreachable",
            primary=True,
        )
    )
    return rows

