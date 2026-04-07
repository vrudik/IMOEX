from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from libs.domain.contracts import (
    AnalystOutput,
    ContinuousSeriesSnapshot,
    FeatureSnapshot,
    RootSeriesSummary,
    SessionSnapshot,
    SkepticReview,
    SkepticVerdict,
    SignalDirection,
    UniverseStatus,
)
from libs.domain.models import SkepticReviewRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository


class SkepticService:
    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def build_reviews(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        feature_snapshots: list[FeatureSnapshot],
        analyst_outputs: list[AnalystOutput],
        as_of: datetime | None = None,
    ) -> list[SkepticReview]:
        timestamp = as_of or datetime.now(UTC)
        reviews = [
            self._build_review(
                root=root,
                session=session,
                continuous=continuous,
                snapshot=snapshot,
                analyst_outputs=[item for item in analyst_outputs if item.horizon == snapshot.horizon],
                as_of=timestamp,
            )
            for snapshot in feature_snapshots
        ]
        try:
            self.repository.upsert_skeptic_reviews(reviews)
        except Exception:
            pass
        return reviews

    def list_latest_reviews(self, *, root_code: str) -> list[SkepticReview]:
        try:
            rows = self.repository.list_latest_skeptic_reviews(root_code=root_code)
        except Exception:
            return []
        return [self._from_record(item) for item in rows]

    def _build_review(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        snapshot: FeatureSnapshot,
        analyst_outputs: list[AnalystOutput],
        as_of: datetime,
    ) -> SkepticReview:
        score = 1.0
        objections: list[str] = []
        flags: list[str] = []

        freshness_floor = min((item.freshness_score for item in analyst_outputs), default=0.95)
        if freshness_floor < 0.7:
            score -= 0.22
            objections.append("stale analyst freshness detected")
            flags.append("stale_data")

        if root.universe_status != UniverseStatus.SELECTED or root.liquidity_score < 0.65:
            penalty = 0.18 if root.universe_status == UniverseStatus.WATCHLIST else 0.32
            score -= penalty
            objections.append("liquidity quality is below active-universe comfort level")
            flags.append("low_liquidity")

        if snapshot.days_to_expiry <= 7 or continuous.roll_risk_flag or session.is_near_expiry:
            score -= 0.22
            objections.append("contract sits inside near-expiry or roll-risk window")
            flags.append("near_expiry")

        macro_output = next((item for item in analyst_outputs if item.analyst == "macro_event"), None)
        if macro_output is not None and macro_output.direction == SignalDirection.NO_EDGE and macro_output.confidence < 0.5:
            score -= 0.1
            objections.append("macro layer remains unconfirmed for the current horizon")
            flags.append("unconfirmed_event")

        directions = Counter(
            item.direction.value for item in analyst_outputs if item.confidence >= 0.58 and item.direction != SignalDirection.NO_EDGE
        )
        contradiction = len(directions) > 1
        if contradiction:
            score -= 0.16
            objections.append("high-confidence analysts disagree on final direction")
            flags.append("cross_analyst_contradiction")

        score = round(max(0.0, min(1.0, score)), 4)
        verdict = self._verdict(score=score, contradiction=contradiction, flags=flags)
        if not objections:
            objections.append("no material skeptic objections for the current horizon")
        if not flags:
            flags.append("quality_ok")

        return SkepticReview(
            review_id=f"SK-{as_of:%Y%m%d%H%M%S}-{root.root_code}-{snapshot.horizon.value}",
            root=root.root_code,
            contract=snapshot.contract,
            horizon=snapshot.horizon,
            generated_at=as_of,
            skeptic_score=score,
            verdict=verdict,
            main_objections=objections,
            data_quality_flags=flags,
        )

    def _verdict(self, *, score: float, contradiction: bool, flags: list[str]) -> SkepticVerdict:
        if contradiction and score <= 0.62:
            return SkepticVerdict.HUMAN_REVIEW
        if score < 0.35:
            return SkepticVerdict.REJECT
        if score < 0.65 or "low_liquidity" in flags or "near_expiry" in flags:
            return SkepticVerdict.SOFT_FAIL
        return SkepticVerdict.PASS

    def _from_record(self, row: SkepticReviewRecord) -> SkepticReview:
        return SkepticReview(
            review_id=row.review_id,
            root=row.root_code,
            contract=row.contract_code,
            horizon=row.horizon,
            generated_at=row.generated_at,
            skeptic_score=float(row.skeptic_score),
            verdict=row.verdict,
            main_objections=self._split_blob(row.main_objections_blob),
            data_quality_flags=self._split_blob(row.data_quality_flags_blob),
        )

    def _split_blob(self, value: str) -> list[str]:
        if not value:
            return []
        return [item for item in value.split("\n") if item]
