from __future__ import annotations

from datetime import UTC, datetime

from libs.domain.contracts import ContinuousSeriesSnapshot, FeatureSnapshot, HorizonCode, SessionSnapshot
from libs.domain.models import FeatureSnapshotRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository


class FeatureService:
    FEATURE_VERSION = "baseline-v1"

    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def build_snapshots(
        self,
        *,
        root_code: str,
        contract_code: str,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        as_of: datetime | None = None,
    ) -> list[FeatureSnapshot]:
        timestamp = as_of or datetime.now(UTC)
        snapshots = [
            self._build_snapshot(
                root_code=root_code,
                contract_code=contract_code,
                horizon=horizon,
                session=session,
                continuous=continuous,
                as_of=timestamp,
            )
            for horizon in HorizonCode
        ]
        try:
            self.repository.upsert_feature_snapshots(snapshots)
        except Exception:
            pass
        return snapshots

    def list_latest_snapshots(self, *, root_code: str) -> list[FeatureSnapshot]:
        try:
            rows = self.repository.list_latest_feature_snapshots(root_code=root_code)
        except Exception:
            return []
        return [self._from_record(item) for item in rows]

    def _build_snapshot(
        self,
        *,
        root_code: str,
        contract_code: str,
        horizon: HorizonCode,
        session: SessionSnapshot,
        continuous: ContinuousSeriesSnapshot,
        as_of: datetime,
    ) -> FeatureSnapshot:
        proximity_to_clearing = None
        if session.is_clearing_window:
            proximity_to_clearing = 0
        elif session.session_end_at >= as_of:
            proximity_to_clearing = max(0, int((session.session_end_at - as_of).total_seconds() // 60))

        horizon_scale = {
            HorizonCode.H1S: 1.0,
            HorizonCode.H3S: 1.35,
            HorizonCode.H2W: 1.75,
            HorizonCode.H4W: 2.15,
        }[horizon]
        roll_pressure = max(0.0, 1.0 - min(1.0, continuous.days_to_last_trade / 20))
        expiry_pressure = max(0.0, 1.0 - min(1.0, continuous.days_to_expiry / 30))
        return_score = round((0.08 + continuous.next_contract_share * 0.12 - roll_pressure * 0.05) * horizon_scale, 6)
        realized_volatility = round((0.14 + roll_pressure * 0.18 + expiry_pressure * 0.06) * horizon_scale, 6)
        atr_ratio = round(0.9 + realized_volatility * 0.8, 6)
        trend_slope = round((0.18 - roll_pressure * 0.07) * horizon_scale, 6)
        vwap_distance_bps = round((12 + continuous.next_contract_share * 40 - roll_pressure * 20) * horizon_scale, 6)

        if continuous.roll_risk_flag:
            breakout_state = "roll_window"
        elif trend_slope >= 0.2:
            breakout_state = "bullish_breakout"
        elif trend_slope <= -0.2:
            breakout_state = "bearish_breakout"
        else:
            breakout_state = "range"

        overnight_gap_regime = "weekend_gap" if session.is_weekend_linked else "normal_gap"
        return FeatureSnapshot(
            snapshot_id=f"FS-{as_of:%Y%m%d%H%M%S}-{root_code}-{contract_code}-{horizon.value}",
            root=root_code,
            contract=contract_code,
            horizon=horizon,
            as_of=as_of,
            feature_version=self.FEATURE_VERSION,
            point_in_time_correct=True,
            session_of_day=session.session_type,
            proximity_to_clearing_minutes=proximity_to_clearing,
            weekend_linked=session.is_weekend_linked,
            days_to_expiry=continuous.days_to_expiry,
            days_to_last_trade=continuous.days_to_last_trade,
            roll_state=continuous.roll_state,
            roll_risk_flag=continuous.roll_risk_flag,
            next_contract_share=continuous.next_contract_share,
            return_score=return_score,
            realized_volatility=realized_volatility,
            atr_ratio=atr_ratio,
            trend_slope=trend_slope,
            vwap_distance_bps=vwap_distance_bps,
            breakout_state=breakout_state,
            overnight_gap_regime=overnight_gap_regime,
        )

    def _from_record(self, row: FeatureSnapshotRecord) -> FeatureSnapshot:
        return FeatureSnapshot(
            snapshot_id=row.snapshot_id,
            root=row.root_code,
            contract=row.contract_code,
            horizon=HorizonCode(row.horizon),
            as_of=row.as_of,
            feature_version=row.feature_version,
            point_in_time_correct=bool(row.point_in_time_correct),
            session_of_day=row.session_of_day,
            proximity_to_clearing_minutes=row.proximity_to_clearing_minutes,
            weekend_linked=bool(row.weekend_linked),
            days_to_expiry=int(row.days_to_expiry),
            days_to_last_trade=int(row.days_to_last_trade),
            roll_state=row.roll_state,
            roll_risk_flag=bool(row.roll_risk_flag),
            next_contract_share=float(row.next_contract_share),
            return_score=float(row.return_score),
            realized_volatility=float(row.realized_volatility),
            atr_ratio=float(row.atr_ratio),
            trend_slope=float(row.trend_slope),
            vwap_distance_bps=float(row.vwap_distance_bps),
            breakout_state=row.breakout_state,
            overnight_gap_regime=row.overnight_gap_regime,
        )
