from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, distinct, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import and_, func

from libs.domain.models import SourceQualityCheckRecord


class SqlAlchemySourceQualityRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_latest_pair(self, *, provider_a: str, provider_b: str) -> SourceQualityCheckRecord | None:
        with self.session_factory() as session:
            stmt = (
                select(SourceQualityCheckRecord)
                .where(SourceQualityCheckRecord.provider_a == provider_a)
                .where(SourceQualityCheckRecord.provider_b == provider_b)
                .order_by(desc(SourceQualityCheckRecord.created_at))
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def list_recent_pair(
        self,
        *,
        provider_a: str,
        provider_b: str,
        contract: str | None = None,
        limit: int = 100,
    ) -> list[SourceQualityCheckRecord]:
        with self.session_factory() as session:
            stmt = (
                select(SourceQualityCheckRecord)
                .where(SourceQualityCheckRecord.provider_a == provider_a)
                .where(SourceQualityCheckRecord.provider_b == provider_b)
            )
            if contract not in (None, ""):
                stmt = stmt.where(SourceQualityCheckRecord.contract == contract)
            stmt = stmt.order_by(desc(SourceQualityCheckRecord.created_at)).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def list_distinct_contracts_pair(
        self,
        *,
        provider_a: str,
        provider_b: str,
        limit: int = 200,
    ) -> list[str]:
        with self.session_factory() as session:
            stmt = (
                select(distinct(SourceQualityCheckRecord.contract))
                .where(SourceQualityCheckRecord.provider_a == provider_a)
                .where(SourceQualityCheckRecord.provider_b == provider_b)
                .order_by(SourceQualityCheckRecord.contract.asc())
                .limit(limit)
            )
            rows = session.execute(stmt).all()
            return [str(item[0]) for item in rows if item and item[0] is not None]

    def count_distinct_contracts_pair(self, *, provider_a: str, provider_b: str) -> int:
        with self.session_factory() as session:
            stmt = (
                select(distinct(SourceQualityCheckRecord.contract))
                .where(SourceQualityCheckRecord.provider_a == provider_a)
                .where(SourceQualityCheckRecord.provider_b == provider_b)
            )
            return len(list(session.execute(stmt).all()))

    def list_latest_per_contract_pair(
        self,
        *,
        provider_a: str,
        provider_b: str,
        limit: int = 200,
    ) -> list[SourceQualityCheckRecord]:
        with self.session_factory() as session:
            latest_per_contract = (
                select(
                    SourceQualityCheckRecord.contract.label("contract"),
                    func.max(SourceQualityCheckRecord.created_at).label("max_created_at"),
                )
                .where(SourceQualityCheckRecord.provider_a == provider_a)
                .where(SourceQualityCheckRecord.provider_b == provider_b)
                .group_by(SourceQualityCheckRecord.contract)
                .subquery()
            )

            stmt = (
                select(SourceQualityCheckRecord)
                .join(
                    latest_per_contract,
                    and_(
                        SourceQualityCheckRecord.contract == latest_per_contract.c.contract,
                        SourceQualityCheckRecord.created_at == latest_per_contract.c.max_created_at,
                    ),
                )
                .where(SourceQualityCheckRecord.provider_a == provider_a)
                .where(SourceQualityCheckRecord.provider_b == provider_b)
                .order_by(desc(SourceQualityCheckRecord.created_at))
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def purge_older_than(self, *, days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=max(0, int(days)))
        with self.session_factory() as session:
            result = session.execute(
                delete(SourceQualityCheckRecord).where(SourceQualityCheckRecord.created_at < cutoff)
            )
            session.commit()
            return int(result.rowcount or 0)

