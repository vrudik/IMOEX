from __future__ import annotations

from datetime import UTC, datetime

from libs.domain.contracts import (
    AnalystKind,
    AnalystOutput,
    AssetClass,
    ContinuousSeriesSnapshot,
    FeatureSnapshot,
    RootSeriesSummary,
    SessionSnapshot,
    SignalDirection,
    UniverseStatus,
)
from libs.domain.models import AnalystOutputRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository


class AnalystService:
    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def build_outputs(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        feature_snapshots: list[FeatureSnapshot],
        as_of: datetime | None = None,
    ) -> list[AnalystOutput]:
        timestamp = as_of or datetime.now(UTC)
        outputs: list[AnalystOutput] = []
        for snapshot in feature_snapshots:
            outputs.extend(
                [
                    self._build_trend_vol(root=root, session=session, continuous=continuous, snapshot=snapshot, as_of=timestamp),
                    self._build_flow_liquidity(root=root, session=session, continuous=continuous, snapshot=snapshot, as_of=timestamp),
                    self._build_oi_roll(root=root, session=session, continuous=continuous, snapshot=snapshot, as_of=timestamp),
                    self._build_macro_event(root=root, session=session, continuous=continuous, snapshot=snapshot, as_of=timestamp),
                ]
            )
        try:
            self.repository.upsert_analyst_outputs(outputs)
        except Exception:
            pass
        return outputs

    def list_latest_outputs(self, *, root_code: str) -> list[AnalystOutput]:
        try:
            rows = self.repository.list_latest_analyst_outputs(root_code=root_code)
        except Exception:
            return []
        return [self._from_record(item) for item in rows]

    def _build_trend_vol(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        snapshot: FeatureSnapshot,
        as_of: datetime,
    ) -> AnalystOutput:
        score = snapshot.trend_slope + snapshot.return_score - snapshot.realized_volatility * 0.4
        direction = self._direction_from_score(score)
        probability = self._probability_from_score(score, floor=0.34)
        confidence = round(
            min(0.93, max(0.4, 0.54 + abs(snapshot.trend_slope) * 0.55 - snapshot.realized_volatility * 0.1)),
            4,
        )
        drivers = [
            f"trend_slope={snapshot.trend_slope:.3f}",
            f"breakout_state={snapshot.breakout_state}",
            f"realized_volatility={snapshot.realized_volatility:.3f}",
        ]
        objections = []
        if snapshot.realized_volatility >= 0.45:
            objections.append("volatility is elevated and can weaken trend persistence")
        if snapshot.breakout_state == "range":
            objections.append("trend signal is still trapped inside a range regime")
        if not objections:
            objections.append("trend regime remains rule-based until richer bar history is wired in")
        invalidation = [
            "trend slope flips sign on the next feature refresh",
            "breakout state falls back into range",
        ]
        return self._output(
            analyst=AnalystKind.TREND_VOL,
            root=root,
            snapshot=snapshot,
            direction=direction,
            probability=probability,
            confidence=confidence,
            drivers=drivers,
            objections=objections,
            invalidation=invalidation,
            freshness_score=self._freshness(snapshot=snapshot, session=session, continuous=continuous),
            as_of=as_of,
        )

    def _build_flow_liquidity(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        snapshot: FeatureSnapshot,
        as_of: datetime,
    ) -> AnalystOutput:
        liquidity_penalty = 0.0 if root.universe_status == UniverseStatus.SELECTED else 0.08
        score = snapshot.vwap_distance_bps / 120 + (root.liquidity_score - 0.5) * 0.45 - liquidity_penalty
        if root.universe_status == UniverseStatus.EXCLUDED:
            score -= 0.16
        direction = self._direction_from_score(score - 0.18)
        probability = self._probability_from_score(score - 0.18, floor=0.35)
        confidence = round(
            min(0.9, max(0.38, 0.48 + root.liquidity_score * 0.35 - liquidity_penalty)),
            4,
        )
        drivers = [
            f"liquidity_score={root.liquidity_score:.3f}",
            f"vwap_distance_bps={snapshot.vwap_distance_bps:.2f}",
            f"universe_status={root.universe_status.value}",
        ]
        objections = []
        if root.universe_status != UniverseStatus.SELECTED:
            objections.append("root is outside the current selected universe and liquidity confidence is discounted")
        if snapshot.proximity_to_clearing_minutes is not None and snapshot.proximity_to_clearing_minutes <= 90:
            objections.append("liquidity conditions can distort near the clearing window")
        if not objections:
            objections.append("true tape and order-book features are still approximated by baseline proxies")
        invalidation = [
            "liquidity ranking drops on the next weekly universe refresh",
            "VWAP displacement mean-reverts back below the flow threshold",
        ]
        return self._output(
            analyst=AnalystKind.FLOW_LIQUIDITY,
            root=root,
            snapshot=snapshot,
            direction=direction,
            probability=probability,
            confidence=confidence,
            drivers=drivers,
            objections=objections,
            invalidation=invalidation,
            freshness_score=self._freshness(snapshot=snapshot, session=session, continuous=continuous),
            as_of=as_of,
        )

    def _build_oi_roll(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        snapshot: FeatureSnapshot,
        as_of: datetime,
    ) -> AnalystOutput:
        score = snapshot.return_score * 0.8 - snapshot.next_contract_share * 0.35
        if continuous.roll_risk_flag:
            score -= 0.18
        if snapshot.days_to_last_trade <= 5:
            score -= 0.12
        direction = self._direction_from_score(score, bullish=0.08, bearish=-0.08)
        probability = self._probability_from_score(score, floor=0.33)
        confidence = round(
            min(
                0.88,
                max(0.36, 0.46 + (0.18 if not continuous.roll_risk_flag else -0.04) + snapshot.return_score * 0.35),
            ),
            4,
        )
        drivers = [
            f"roll_state={snapshot.roll_state}",
            f"next_contract_share={snapshot.next_contract_share:.2f}",
            f"days_to_last_trade={snapshot.days_to_last_trade}",
        ]
        objections = []
        if continuous.roll_risk_flag:
            objections.append("root is inside the roll-risk window and OI-style inference is penalized")
        if snapshot.days_to_last_trade <= 7:
            objections.append("distance to last trade date is short for a stable carry read")
        if not objections:
            objections.append("OI logic currently uses roll proxies until exchange OI feed is connected")
        invalidation = [
            "next contract share accelerates above the current roll threshold",
            "days to last trade compress into the guarded expiry window",
        ]
        return self._output(
            analyst=AnalystKind.OI_ROLL,
            root=root,
            snapshot=snapshot,
            direction=direction,
            probability=probability,
            confidence=confidence,
            drivers=drivers,
            objections=objections,
            invalidation=invalidation,
            freshness_score=self._freshness(snapshot=snapshot, session=session, continuous=continuous),
            as_of=as_of,
        )

    def _build_macro_event(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        snapshot: FeatureSnapshot,
        as_of: datetime,
    ) -> AnalystOutput:
        score = 0.02
        if root.asset_class == AssetClass.CURRENCY:
            score += 0.08
        if root.asset_class == AssetClass.COMMODITY:
            score -= 0.02
        if snapshot.overnight_gap_regime == "weekend_gap":
            score -= 0.12
        if session.is_clearing_window:
            score -= 0.08
        if continuous.roll_risk_flag:
            score -= 0.05
        direction = self._direction_from_score(score, bullish=0.09, bearish=-0.09)
        probability = self._probability_from_score(score, floor=0.31)
        confidence = round(
            min(0.82, max(0.34, 0.44 + (0.08 if root.asset_class == AssetClass.CURRENCY else 0.0))),
            4,
        )
        drivers = [
            f"asset_class={root.asset_class.value}",
            f"overnight_gap_regime={snapshot.overnight_gap_regime}",
            f"weekend_linked={str(session.is_weekend_linked).lower()}",
        ]
        objections = []
        if snapshot.overnight_gap_regime == "weekend_gap":
            objections.append("weekend-linked gap regime lowers macro confidence")
        if session.is_clearing_window:
            objections.append("macro interpretation around clearing windows is intentionally conservative")
        if not objections:
            objections.append("macro layer still uses regime flags until event calendar adapters are live")
        invalidation = [
            "macro regime flags change on the next calendar refresh",
            "weekend-linked session mapping is removed for the current trading day",
        ]
        return self._output(
            analyst=AnalystKind.MACRO_EVENT,
            root=root,
            snapshot=snapshot,
            direction=direction,
            probability=probability,
            confidence=confidence,
            drivers=drivers,
            objections=objections,
            invalidation=invalidation,
            freshness_score=self._freshness(snapshot=snapshot, session=session, continuous=continuous),
            as_of=as_of,
        )

    def _output(
        self,
        *,
        analyst: AnalystKind,
        root: RootSeriesSummary,
        snapshot: FeatureSnapshot,
        direction: SignalDirection,
        probability: float,
        confidence: float,
        drivers: list[str],
        objections: list[str],
        invalidation: list[str],
        freshness_score: float,
        as_of: datetime,
    ) -> AnalystOutput:
        return AnalystOutput(
            output_id=f"AO-{as_of:%Y%m%d%H%M%S}-{root.root_code}-{snapshot.horizon.value}-{analyst.value}",
            root=root.root_code,
            contract=snapshot.contract,
            horizon=snapshot.horizon,
            analyst=analyst,
            generated_at=as_of,
            direction=direction,
            probability=probability,
            confidence=confidence,
            drivers=drivers,
            objections=objections,
            invalidation_conditions=invalidation,
            freshness_score=freshness_score,
        )

    def _from_record(self, row: AnalystOutputRecord) -> AnalystOutput:
        return AnalystOutput(
            output_id=row.output_id,
            root=row.root_code,
            contract=row.contract_code,
            horizon=row.horizon,
            analyst=row.analyst,
            generated_at=row.generated_at,
            direction=row.direction,
            probability=float(row.probability),
            confidence=float(row.confidence),
            drivers=self._split_blob(row.drivers_blob),
            objections=self._split_blob(row.objections_blob),
            invalidation_conditions=self._split_blob(row.invalidation_conditions_blob),
            freshness_score=float(row.freshness_score),
        )

    def _freshness(
        self,
        *,
        snapshot: FeatureSnapshot,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
    ) -> float:
        freshness = 0.95 if snapshot.point_in_time_correct else 0.58
        if session.is_weekend_linked:
            freshness -= 0.04
        if continuous.roll_risk_flag:
            freshness -= 0.05
        return round(max(0.4, freshness), 4)

    def _direction_from_score(
        self,
        score: float,
        *,
        bullish: float = 0.12,
        bearish: float = -0.12,
    ) -> SignalDirection:
        if score >= bullish:
            return SignalDirection.BULLISH
        if score <= bearish:
            return SignalDirection.BEARISH
        return SignalDirection.NO_EDGE

    def _probability_from_score(self, score: float, *, floor: float) -> float:
        return round(min(0.86, max(floor, 0.5 + abs(score) * 0.55)), 4)

    def _split_blob(self, value: str) -> list[str]:
        if not value:
            return []
        return [item for item in value.split("\n") if item]
