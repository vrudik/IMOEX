from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from libs.quality.repository import SqlAlchemySourceQualityRepository
from libs.utils.db import database_available, get_session_factory

router = APIRouter(tags=["quality"])


class SourceQualityCheckResponse(BaseModel):
    provider_a: str
    provider_b: str
    contract: str
    from_ts: str
    till_ts: str
    count_a: int
    count_b: int
    overlap_count: int
    missing_in_a: int
    missing_in_b: int
    mismatch_ohlc: int
    mismatch_volume: int
    mismatch_rate_overlap: float
    created_at: str


class QualityPairSummary(BaseModel):
    provider_a: str
    provider_b: str
    latest_at: str | None
    latest_contract: str | None
    contracts_count: int


@router.get("/quality/source-checks", response_model=list[SourceQualityCheckResponse])
async def list_source_quality_checks(
    provider_a: str = "moex",
    provider_b: str = "finam",
    contract: str | None = None,
    limit: int = 50,
) -> list[SourceQualityCheckResponse]:
    if not database_available():
        return []
    repo = SqlAlchemySourceQualityRepository(get_session_factory())
    rows = repo.list_recent_pair(
        provider_a=provider_a,
        provider_b=provider_b,
        contract=contract,
        limit=min(max(int(limit), 1), 500),
    )
    return [SourceQualityCheckResponse.model_validate(row.to_dict()) for row in rows]


@router.get("/quality/source-checks-latest", response_model=list[SourceQualityCheckResponse])
async def list_latest_source_quality_checks(
    provider_a: str = "moex",
    provider_b: str = "finam",
    limit: int = 200,
) -> list[SourceQualityCheckResponse]:
    if not database_available():
        return []
    repo = SqlAlchemySourceQualityRepository(get_session_factory())
    rows = repo.list_latest_per_contract_pair(
        provider_a=provider_a,
        provider_b=provider_b,
        limit=min(max(int(limit), 1), 2000),
    )
    return [SourceQualityCheckResponse.model_validate(row.to_dict()) for row in rows]


@router.get("/quality/contracts", response_model=list[str])
async def list_quality_contracts(
    provider_a: str = "moex",
    provider_b: str = "finam",
    limit: int = 200,
) -> list[str]:
    if not database_available():
        return []
    repo = SqlAlchemySourceQualityRepository(get_session_factory())
    return repo.list_distinct_contracts_pair(
        provider_a=provider_a,
        provider_b=provider_b,
        limit=min(max(int(limit), 1), 1000),
    )


@router.get("/quality/summary", response_model=QualityPairSummary)
async def quality_summary(
    provider_a: str = "moex",
    provider_b: str = "finam",
) -> QualityPairSummary:
    if not database_available():
        return QualityPairSummary(
            provider_a=provider_a,
            provider_b=provider_b,
            latest_at=None,
            latest_contract=None,
            contracts_count=0,
        )
    repo = SqlAlchemySourceQualityRepository(get_session_factory())
    latest = repo.get_latest_pair(provider_a=provider_a, provider_b=provider_b)
    return QualityPairSummary(
        provider_a=provider_a,
        provider_b=provider_b,
        latest_at=latest.created_at if latest else None,
        latest_contract=latest.contract if latest else None,
        contracts_count=repo.count_distinct_contracts_pair(provider_a=provider_a, provider_b=provider_b),
    )

