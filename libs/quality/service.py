from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from libs.adapters.contracts import Bar
from libs.domain.models import SourceQualityCheckRecord
from libs.quality.repository import SqlAlchemySourceQualityRepository


class ShadowComparisonService:
    def __init__(
        self,
        repository: SqlAlchemySourceQualityRepository,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.repository = repository
        self.session_factory = session_factory

    def compare_bars(
        self,
        *,
        provider_a: str,
        provider_b: str,
        contract: str,
        bars_a: list[Bar],
        bars_b: list[Bar],
        persist: bool = True,
    ) -> SourceQualityCheckRecord:
        index_a = {(item.start_at, item.end_at): item for item in bars_a}
        index_b = {(item.start_at, item.end_at): item for item in bars_b}
        keys_a = set(index_a)
        keys_b = set(index_b)
        overlap_keys = sorted(keys_a & keys_b)

        mismatch_ohlc = 0
        mismatch_volume = 0
        mismatch_any = 0
        for key in overlap_keys:
            left = index_a[key]
            right = index_b[key]
            ohlc_mismatch = any(
                abs(left_value - right_value) > 1e-9
                for left_value, right_value in (
                    (left.open, right.open),
                    (left.high, right.high),
                    (left.low, right.low),
                    (left.close, right.close),
                )
            )
            volume_mismatch = abs(left.volume - right.volume) > 1e-9
            if ohlc_mismatch:
                mismatch_ohlc += 1
            if volume_mismatch:
                mismatch_volume += 1
            if ohlc_mismatch or volume_mismatch:
                mismatch_any += 1

        all_times = [item.start_at for item in bars_a] + [item.start_at for item in bars_b]
        all_end_times = [item.end_at for item in bars_a] + [item.end_at for item in bars_b]
        now = datetime.now(UTC)
        record = SourceQualityCheckRecord(
            provider_a=provider_a,
            provider_b=provider_b,
            contract=contract,
            from_ts=min(all_times) if all_times else now,
            till_ts=max(all_end_times) if all_end_times else now,
            count_a=len(bars_a),
            count_b=len(bars_b),
            overlap_count=len(overlap_keys),
            missing_in_a=len(keys_b - keys_a),
            missing_in_b=len(keys_a - keys_b),
            mismatch_ohlc=mismatch_ohlc,
            mismatch_volume=mismatch_volume,
            mismatch_rate_overlap=(mismatch_any / len(overlap_keys)) if overlap_keys else 0.0,
            created_at=now,
        )
        if persist:
            record = self._save(record)
        return record

    def _save(self, record: SourceQualityCheckRecord) -> SourceQualityCheckRecord:
        snapshot = {
            "provider_a": record.provider_a,
            "provider_b": record.provider_b,
            "contract": record.contract,
            "from_ts": record.from_ts,
            "till_ts": record.till_ts,
            "count_a": record.count_a,
            "count_b": record.count_b,
            "overlap_count": record.overlap_count,
            "missing_in_a": record.missing_in_a,
            "missing_in_b": record.missing_in_b,
            "mismatch_ohlc": record.mismatch_ohlc,
            "mismatch_volume": record.mismatch_volume,
            "mismatch_rate_overlap": record.mismatch_rate_overlap,
            "created_at": record.created_at,
        }
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        return SourceQualityCheckRecord(**snapshot)
