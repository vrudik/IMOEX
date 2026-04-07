from __future__ import annotations

from datetime import UTC, datetime

from libs.domain.contracts import (
    AnalystKind,
    AnalystOutput,
    FeatureSnapshot,
    FinalSignalDetail,
    RootSeriesSummary,
    SignalDirection,
    SignalStatus,
    SkepticReview,
    SkepticVerdict,
)


class ArbiterService:
    SIGNAL_VERSION = 2

    def build_signal(
        self,
        *,
        root: RootSeriesSummary,
        snapshot: FeatureSnapshot,
        analyst_outputs: list[AnalystOutput],
        skeptic_review: SkepticReview,
        generated_at: datetime | None = None,
    ) -> FinalSignalDetail | None:
        if not analyst_outputs:
            return None

        probs = self._aggregate_probabilities(analyst_outputs=analyst_outputs, skeptic_review=skeptic_review)
        direction = self._final_direction(probs)
        confidence = self._confidence(probs=probs, skeptic_review=skeptic_review, analyst_outputs=analyst_outputs)
        status = SignalStatus.INVALIDATED if skeptic_review.verdict == SkepticVerdict.REJECT else SignalStatus.ACTIVE
        roll_risk = round(min(1.0, snapshot.next_contract_share * 0.6 + (0.2 if snapshot.roll_risk_flag else 0.0)), 4)
        expiry_risk = round(min(1.0, max(0.0, 1.0 - snapshot.days_to_expiry / 30)), 4)
        freshness_score = round(
            min(0.98, max(0.4, min(item.freshness_score for item in analyst_outputs) * skeptic_review.skeptic_score + 0.08)),
            4,
        )
        priority_score = self._priority(
            confidence=confidence,
            skeptic_review=skeptic_review,
            direction=direction,
            freshness_score=freshness_score,
            root=root,
        )

        if direction == SignalDirection.NO_EDGE and confidence < 0.52 and skeptic_review.verdict == SkepticVerdict.PASS:
            return None

        generated = generated_at or snapshot.as_of or datetime.now(UTC)
        drivers = self._drivers(analyst_outputs=analyst_outputs, direction=direction, root=root)
        objections = self._objections(analyst_outputs=analyst_outputs, skeptic_review=skeptic_review, direction=direction)
        invalidation = self._invalidation(analyst_outputs=analyst_outputs, skeptic_review=skeptic_review)
        summary = self._summary(direction=direction, skeptic_review=skeptic_review, snapshot=snapshot)
        signal_id = f"SIG-{generated:%Y-%m-%d}-{root.root_code}-{snapshot.horizon.value}-{priority_score:06d}"

        return FinalSignalDetail(
            signal_id=signal_id,
            version=self.SIGNAL_VERSION,
            root=root.root_code,
            contract=snapshot.contract,
            horizon=snapshot.horizon,
            status=status,
            direction_final=direction,
            probability_up=probs["up"],
            probability_down=probs["down"],
            probability_no_edge=probs["no_edge"],
            confidence_final=confidence,
            priority_score=priority_score,
            roll_risk=roll_risk,
            expiry_risk=expiry_risk,
            skeptic_score=skeptic_review.skeptic_score,
            skeptic_verdict=skeptic_review.verdict,
            generated_at=generated,
            freshness_score=freshness_score,
            summary=summary,
            drivers=drivers,
            objections=objections,
            invalidation_conditions=invalidation,
            data_sources=self._data_sources(root=root),
        )

    def _aggregate_probabilities(
        self,
        *,
        analyst_outputs: list[AnalystOutput],
        skeptic_review: SkepticReview,
    ) -> dict[str, float]:
        weights = {
            AnalystKind.TREND_VOL: 0.32,
            AnalystKind.FLOW_LIQUIDITY: 0.23,
            AnalystKind.OI_ROLL: 0.25,
            AnalystKind.MACRO_EVENT: 0.20,
        }
        bull = 0.0
        bear = 0.0
        no_edge = 0.0
        for output in analyst_outputs:
            weight = weights.get(output.analyst, 0.2)
            contribution = weight * output.probability * output.confidence
            if output.direction == SignalDirection.BULLISH:
                bull += contribution
                no_edge += weight * (1 - output.probability) * 0.18
            elif output.direction == SignalDirection.BEARISH:
                bear += contribution
                no_edge += weight * (1 - output.probability) * 0.18
            else:
                no_edge += contribution + weight * 0.08

        skeptic_penalty = 1.0 - skeptic_review.skeptic_score
        bull *= skeptic_review.skeptic_score
        bear *= skeptic_review.skeptic_score
        no_edge += skeptic_penalty * 0.45
        total = bull + bear + no_edge
        if total <= 0:
            return {"up": 0.33, "down": 0.33, "no_edge": 0.34}
        up = round(bull / total, 4)
        down = round(bear / total, 4)
        flat = round(max(0.0, 1.0 - up - down), 4)
        return {"up": up, "down": down, "no_edge": flat}

    def _final_direction(self, probs: dict[str, float]) -> SignalDirection:
        if probs["up"] >= max(probs["down"], probs["no_edge"]) and probs["up"] >= 0.42:
            return SignalDirection.BULLISH
        if probs["down"] >= max(probs["up"], probs["no_edge"]) and probs["down"] >= 0.42:
            return SignalDirection.BEARISH
        return SignalDirection.NO_EDGE

    def _confidence(
        self,
        *,
        probs: dict[str, float],
        skeptic_review: SkepticReview,
        analyst_outputs: list[AnalystOutput],
    ) -> float:
        ordered = sorted(probs.values(), reverse=True)
        spread = ordered[0] - ordered[1]
        avg_conf = sum(item.confidence for item in analyst_outputs) / max(1, len(analyst_outputs))
        return round(min(0.95, max(0.35, avg_conf * 0.55 + skeptic_review.skeptic_score * 0.35 + spread * 0.4)), 4)

    def _priority(
        self,
        *,
        confidence: float,
        skeptic_review: SkepticReview,
        direction: SignalDirection,
        freshness_score: float,
        root: RootSeriesSummary,
    ) -> int:
        base = confidence * 100 + freshness_score * 8 + root.liquidity_score * 12
        if direction != SignalDirection.NO_EDGE:
            base += 10
        if skeptic_review.verdict == SkepticVerdict.SOFT_FAIL:
            base -= 12
        elif skeptic_review.verdict == SkepticVerdict.HUMAN_REVIEW:
            base -= 18
        elif skeptic_review.verdict == SkepticVerdict.REJECT:
            base -= 28
        return int(max(1, min(99, round(base))))

    def _drivers(
        self,
        *,
        analyst_outputs: list[AnalystOutput],
        direction: SignalDirection,
        root: RootSeriesSummary,
    ) -> list[str]:
        preferred = [
            driver
            for item in analyst_outputs
            if item.direction == direction and direction != SignalDirection.NO_EDGE
            for driver in item.drivers
        ]
        if direction == SignalDirection.NO_EDGE:
            preferred = [driver for item in analyst_outputs for driver in item.drivers[:1]]
        preferred.extend(root.selection_reasons[:1])
        return self._dedupe(preferred)[:5]

    def _objections(
        self,
        *,
        analyst_outputs: list[AnalystOutput],
        skeptic_review: SkepticReview,
        direction: SignalDirection,
    ) -> list[str]:
        objections = list(skeptic_review.main_objections)
        objections.extend(
            objection
            for item in analyst_outputs
            if direction == SignalDirection.NO_EDGE or item.direction != direction
            for objection in item.objections[:2]
        )
        return self._dedupe(objections)[:6]

    def _invalidation(
        self,
        *,
        analyst_outputs: list[AnalystOutput],
        skeptic_review: SkepticReview,
    ) -> list[str]:
        invalidation = [condition for item in analyst_outputs for condition in item.invalidation_conditions[:1]]
        invalidation.extend(flag.replace("_", " ") for flag in skeptic_review.data_quality_flags if flag != "quality_ok")
        return self._dedupe(invalidation)[:6]

    def _summary(
        self,
        *,
        direction: SignalDirection,
        skeptic_review: SkepticReview,
        snapshot: FeatureSnapshot,
    ) -> str:
        if direction == SignalDirection.BULLISH:
            tone = "Analyst consensus remains net bullish"
        elif direction == SignalDirection.BEARISH:
            tone = "Analyst consensus remains net bearish"
        else:
            tone = "Consensus is mixed and arbiter keeps the setup near no-edge"
        return (
            f"{tone}; horizon={snapshot.horizon.value}, roll_state={snapshot.roll_state}, "
            f"skeptic={skeptic_review.verdict.value}, skeptic_score={skeptic_review.skeptic_score:.2f}."
        )

    def _data_sources(self, *, root: RootSeriesSummary) -> list[str]:
        sources = ["moex", root.primary_provider]
        if root.secondary_provider:
            sources.append(root.secondary_provider)
        return self._dedupe(sources)

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
