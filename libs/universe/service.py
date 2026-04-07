from __future__ import annotations

from dataclasses import dataclass

from libs.domain.contracts import AssetClass, ManualOverrideState, RootSeriesSummary, UniverseStatus
from libs.domain.models import ContractMetaRecord, RootSeriesRecord


@dataclass(frozen=True)
class UniverseCandidate:
    root: RootSeriesRecord
    contracts: list[ContractMetaRecord]
    liquidity_score: float
    manual_override: ManualOverrideState
    universe_status: UniverseStatus
    selection_reasons: tuple[str, ...]


class UniverseService:
    def __init__(self, *, top_n: int = 12) -> None:
        self.top_n = top_n

    def rank(
        self,
        *,
        roots: list[RootSeriesRecord],
        contracts_by_root: dict[str, list[ContractMetaRecord]],
    ) -> list[UniverseCandidate]:
        scored: list[UniverseCandidate] = []
        for root in roots:
            contracts = contracts_by_root.get(root.root_code, [])
            score = self._score_root(root, contracts)
            override = self._manual_override(root)
            scored.append(
                UniverseCandidate(
                    root=root,
                    contracts=contracts,
                    liquidity_score=score,
                    manual_override=override,
                    universe_status=UniverseStatus.WATCHLIST,
                    selection_reasons=(),
                )
            )

        selected_codes = self._select_universe(scored)
        results: list[UniverseCandidate] = []
        for candidate in sorted(scored, key=lambda item: (-item.liquidity_score, item.root.root_code)):
            status = UniverseStatus.SELECTED if candidate.root.root_code in selected_codes else UniverseStatus.WATCHLIST
            reasons = list(self._base_reasons(candidate))
            if candidate.manual_override == ManualOverrideState.DENY:
                status = UniverseStatus.EXCLUDED
                reasons.insert(0, "manually denied from the active universe")
            elif candidate.manual_override == ManualOverrideState.ALLOW:
                reasons.insert(0, "manually allowed into the active universe")
            elif candidate.manual_override == ManualOverrideState.LOCK:
                reasons.insert(0, "selection is locked for this root series")
            elif status == UniverseStatus.SELECTED:
                reasons.insert(0, "selected by weekly liquidity ranking")
            else:
                reasons.insert(0, "kept on watchlist below current selection threshold")

            results.append(
                UniverseCandidate(
                    root=candidate.root,
                    contracts=candidate.contracts,
                    liquidity_score=candidate.liquidity_score,
                    manual_override=candidate.manual_override,
                    universe_status=status,
                    selection_reasons=tuple(reasons),
                )
            )
        return results

    def apply_to_summary(self, summary: RootSeriesSummary, candidate: UniverseCandidate, rank: int) -> RootSeriesSummary:
        return summary.model_copy(
            update={
                "liquidity_rank": rank,
                "liquidity_score": candidate.liquidity_score,
                "universe_status": candidate.universe_status,
                "manual_override": candidate.manual_override,
                "selection_reasons": list(candidate.selection_reasons),
            },
            deep=True,
        )

    def _score_root(self, root: RootSeriesRecord, contracts: list[ContractMetaRecord]) -> float:
        inverse_rank = max(0.0, 1.0 - (max(1, int(root.liquidity_rank)) - 1) * 0.12)
        coverage_score = min(1.0, len(contracts) / 2)
        active_contract = next((item for item in contracts if item.contract_code == root.active_contract), None)
        next_contract = next((item for item in contracts if item.contract_code == root.next_contract), None)
        front_stability = 0.5
        ladder_strength = 0.5
        if active_contract is not None:
            front_stability = min(1.0, max(0.0, active_contract.last_trade_date.toordinal() - active_contract.expiry_date.toordinal() + 30) / 30)
            front_stability = max(front_stability, 0.55)
        if active_contract is not None and next_contract is not None:
            gap_days = max(1, (next_contract.last_trade_date - active_contract.last_trade_date).days)
            ladder_strength = min(1.0, gap_days / 120)
        manual_bonus = 0.0
        if root.manual_allow:
            manual_bonus += 0.08
        if root.lock_selected:
            manual_bonus += 0.05
        if root.manual_deny:
            manual_bonus -= 0.4
        score = 0.5 * inverse_rank + 0.2 * coverage_score + 0.15 * front_stability + 0.15 * ladder_strength + manual_bonus
        if float(root.liquidity_score or 0) > 0:
            score = max(score, float(root.liquidity_score))
        return round(max(0.0, min(1.0, score)), 6)

    def _manual_override(self, root: RootSeriesRecord) -> ManualOverrideState:
        if root.manual_deny:
            return ManualOverrideState.DENY
        if root.lock_selected:
            return ManualOverrideState.LOCK
        if root.manual_allow:
            return ManualOverrideState.ALLOW
        return ManualOverrideState.NONE

    def _select_universe(self, candidates: list[UniverseCandidate]) -> set[str]:
        sorted_candidates = sorted(candidates, key=lambda item: (-item.liquidity_score, item.root.root_code))
        selected: list[UniverseCandidate] = []

        for candidate in sorted_candidates:
            if candidate.manual_override == ManualOverrideState.DENY:
                continue
            if candidate.manual_override in {ManualOverrideState.ALLOW, ManualOverrideState.LOCK}:
                selected.append(candidate)

        covered_classes = {item.root.asset_class for item in selected}
        for asset_class in AssetClass:
            if asset_class.value in covered_classes:
                continue
            best = next(
                (
                    item
                    for item in sorted_candidates
                    if item.root.asset_class == asset_class.value
                    and item.manual_override != ManualOverrideState.DENY
                    and item.root.root_code not in {chosen.root.root_code for chosen in selected}
                ),
                None,
            )
            if best is not None:
                selected.append(best)

        for candidate in sorted_candidates:
            if len(selected) >= self.top_n:
                break
            if candidate.manual_override == ManualOverrideState.DENY:
                continue
            if candidate.root.root_code in {item.root.root_code for item in selected}:
                continue
            selected.append(candidate)
        return {item.root.root_code for item in selected}

    def _base_reasons(self, candidate: UniverseCandidate) -> list[str]:
        reasons = [
            f"liquidity_score={candidate.liquidity_score:.3f}",
            f"contracts_covered={len(candidate.contracts)}",
            f"asset_class={candidate.root.asset_class}",
        ]
        if candidate.root.next_contract:
            reasons.append(f"front_next_pair={candidate.root.active_contract}->{candidate.root.next_contract}")
        return reasons
