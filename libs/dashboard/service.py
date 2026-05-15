from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta

from libs.adapters.contracts import Bar
from libs.dashboard.contracts import (
    AttentionInboxItem,
    DashboardKpi,
    MarketDataFeedStatus,
    MarketAvailabilitySnapshot,
    ModelRoleAssignment,
    DashboardQualityPair,
    DashboardSnapshot,
    ConfidenceDecomposition,
    ConfidenceFactor,
    DecisionTimelineItem,
    HistoricalSetup,
    InstrumentChartOverlay,
    HorizonPulsePoint,
    InstrumentChartPoint,
    InstrumentChartSeries,
    InstrumentMarketSnapshot,
    HorizonComparisonItem,
    HorizonComparisonSnapshot,
    JournalDecisionLogItem,
    JournalTagSummary,
    JournalWorkspaceEntry,
    JournalWorkspaceSnapshot,
    ReviewBundle,
    ReferenceSyncStatus,
    SignalChangeSummary,
    RuntimeControlPanel,
    SignalMetricBar,
    SignalTimelineEvent,
    SignalVisualSnapshot,
    SystemConfidencePanel,
    TrustRibbon,
    TrustRibbonItem,
    WatchlistEntry,
    WorkspaceActionItem,
    WorkspaceSignalSnapshot,
    WorkspaceRootPulse,
    WorkspaceSnapshot,
)
from libs.domain.contracts import EvaluationSummary, FinalSignalCard, FinalSignalDetail, JournalEntryKind, SessionType, SignalStatus
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService, get_contract_master_service
from libs.evaluation.service import EvaluationService
from libs.marketdata.service import MarketDataService, get_market_data_service
from libs.observability.service import ObservabilityService
from libs.quality.repository import SqlAlchemySourceQualityRepository
from libs.runtime.service import RuntimeControlService
from libs.signals.service import SignalService
from libs.utils.config import settings
from libs.utils.db import get_session_factory


class DashboardService:
    MARKET_TIMEFRAME_HORIZONS: dict[str, tuple[str, ...]] = {
        "1D": ("H1S", "H3S"),
        "1W": ("H2W",),
        "1M": ("H4W",),
    }

    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        quality_repository: SqlAlchemySourceQualityRepository,
        *,
        contract_service: ContractMasterService | None = None,
        signal_service: SignalService | None = None,
        evaluation_service: EvaluationService | None = None,
        observability_service: ObservabilityService | None = None,
        runtime_control_service: RuntimeControlService | None = None,
        market_data_service: MarketDataService | None = None,
    ) -> None:
        self.repository = repository
        self.quality_repository = quality_repository
        self.contract_service = contract_service or get_contract_master_service()
        self.signal_service = signal_service or SignalService(repository)
        self.evaluation_service = evaluation_service or EvaluationService(repository)
        self.observability_service = observability_service or ObservabilityService(repository)
        self.runtime_control_service = runtime_control_service or RuntimeControlService(repository)
        self.market_data_service = market_data_service or get_market_data_service()

    def build_snapshot(self, *, root: str | None = None) -> DashboardSnapshot:
        roots = self.contract_service.list_roots()
        selected_root = root or (roots[0].root_code if roots else "Si")
        if roots and all(item.root_code.upper() != selected_root.upper() for item in roots):
            selected_root = roots[0].root_code

        generated_at = datetime.now(UTC)
        root_details = self.contract_service.get_root_deep_dive(selected_root) if roots else None
        spotlight_signals = self._list_signals(
            root=selected_root,
            status=SignalStatus.ACTIVE,
            limit=6,
            seed_root_details=root_details,
        )
        recent_signals = self._list_signals(limit=12)
        evaluation = self.evaluation_service.summarize(root=selected_root, top_k=3, limit=200)
        admin_health = self.observability_service.admin_health()
        quality_pairs = [self._quality_pair("moex", "finam"), self._quality_pair("moex", "bcs")]
        kpis = self._build_kpis(
            spotlight_signals=spotlight_signals,
            evaluation=evaluation,
            admin_health=admin_health,
            root_details=root_details,
        )
        control_panel = self._build_control_panel(
            generated_at=generated_at,
            root_details=root_details,
            admin_health=admin_health,
        )
        trust_ribbon = self._build_trust_ribbon(control_panel=control_panel, admin_health=admin_health)
        system_confidence = self._build_system_confidence(
            control_panel=control_panel,
            admin_health=admin_health,
            evaluation=evaluation,
            active_signals=spotlight_signals,
        )

        return DashboardSnapshot(
            generated_at=generated_at,
            selected_root=selected_root,
            roots=roots,
            root_details=root_details,
            spotlight_signals=spotlight_signals,
            recent_signals=recent_signals,
            evaluation=evaluation,
            admin_health=admin_health,
            quality_pairs=quality_pairs,
            kpis=kpis,
            control_panel=control_panel,
            trust_ribbon=trust_ribbon,
            system_confidence=system_confidence,
        )

    def build_workspace_snapshot(
        self,
        *,
        root: str | None = None,
        signal_id: str | None = None,
    ) -> WorkspaceSnapshot:
        roots = self.contract_service.list_roots()
        selected_root = root or (roots[0].root_code if roots else "Si")
        if roots and all(item.root_code.upper() != selected_root.upper() for item in roots):
            selected_root = roots[0].root_code

        generated_at = datetime.now(UTC)
        root_details = self.contract_service.get_root_deep_dive(selected_root) if roots else None
        signal_lane = self._list_signals(
            root=selected_root,
            status=SignalStatus.ACTIVE,
            limit=8,
            seed_root_details=root_details,
        )
        if not signal_lane:
            signal_lane = self._list_signals(root=selected_root, limit=8, seed_root_details=root_details)

        focus_signal = self._resolve_focus_signal(
            selected_root=selected_root,
            signal_id=signal_id,
            signal_lane=signal_lane,
            root_details=root_details,
        )
        selected_signal_id = focus_signal.signal_id if focus_signal is not None else None
        evaluation = self.evaluation_service.summarize(root=selected_root, top_k=3, limit=200)
        admin_health = self.observability_service.admin_health()
        quality_pairs = [self._quality_pair("moex", "finam"), self._quality_pair("moex", "bcs")]
        all_active = self._list_signals(status=SignalStatus.ACTIVE, limit=max(len(roots) * 6, 20))
        control_panel = self._build_control_panel(
            generated_at=generated_at,
            root_details=root_details,
            admin_health=admin_health,
        )
        watchlist = self._build_watchlist()
        trust_ribbon = self._build_trust_ribbon(control_panel=control_panel, admin_health=admin_health)
        focus_signal_diff = self._build_signal_change_summary(focus_signal)
        focus_confidence = self._build_confidence_decomposition(focus_signal, root_details=root_details)
        decision_log_preview = self._build_decision_timeline(focus_signal)
        workspace_mode = self._workspace_mode(focus_signal=focus_signal, watchlist=watchlist)
        comparison = self._build_horizon_comparison(selected_root=selected_root, root_details=root_details)
        system_confidence = self._build_system_confidence(
            control_panel=control_panel,
            admin_health=admin_health,
            evaluation=evaluation,
            active_signals=signal_lane,
        )
        market_signal = self._resolve_market_signal_for_root(
            root=selected_root,
            root_details=root_details,
            preferred=focus_signal,
        )
        market_snapshot, market_availability = self._build_instrument_market_state(
            root_details=root_details,
            control_panel=control_panel,
            generated_at=generated_at,
            signal=market_signal,
        )
        pulses = self._build_pulses(
            roots=roots,
            active_signals=all_active,
            selected_root=selected_root,
            generated_at=generated_at,
        )
        attention_inbox = self._build_attention_inbox(
            active_signals=all_active or signal_lane,
            selected_root=selected_root,
            selected_signal_id=selected_signal_id,
            watchlist=watchlist,
            pulses=pulses,
            market_snapshot=market_snapshot,
            focus_signal_diff=focus_signal_diff,
        )

        return WorkspaceSnapshot(
            generated_at=generated_at,
            selected_root=selected_root,
            selected_signal_id=selected_signal_id,
            roots=roots,
            pulses=pulses,
            market_snapshot=market_snapshot,
            market_availability=market_availability,
            signal_lane=signal_lane,
            focus_signal=focus_signal,
            root_details=root_details,
            evaluation=evaluation,
            admin_health=admin_health,
            quality_pairs=quality_pairs,
            control_panel=control_panel,
            trust_ribbon=trust_ribbon,
            system_confidence=system_confidence,
            workspace_mode=workspace_mode,
            watchlist=watchlist,
            attention_inbox=attention_inbox,
            comparison=comparison,
            action_items=self._build_workspace_actions(
                focus_signal=focus_signal,
                root_details=root_details,
                evaluation=evaluation,
                admin_health=admin_health,
            ),
            focus_visual=(
                self._build_signal_visual(signal=focus_signal, root_details=root_details)
                if focus_signal is not None
                else None
            ),
            focus_signal_diff=focus_signal_diff,
            focus_confidence=focus_confidence,
            decision_log_preview=decision_log_preview,
            review_bundle=self._build_review_bundle(roots=roots),
        )

    def build_signal_snapshot(self, *, signal_id: str) -> WorkspaceSignalSnapshot | None:
        signal = self._materialize_signal_detail(signal_id)
        if signal is None:
            return None

        roots = self.contract_service.list_roots()
        root_details = self.contract_service.get_root_deep_dive(signal.root)
        related_signals = self._list_signals(
            root=signal.root,
            limit=6,
            seed_root_details=root_details,
        )
        related_signals = [item for item in related_signals if item.signal_id != signal.signal_id][:5]
        generated_at = datetime.now(UTC)
        evaluation = self.evaluation_service.summarize(root=signal.root, top_k=3, limit=200)
        admin_health = self.observability_service.admin_health()
        control_panel = self._build_control_panel(
            generated_at=generated_at,
            root_details=root_details,
            admin_health=admin_health,
        )
        market_snapshot, market_availability = self._build_instrument_market_state(
            root_details=root_details,
            control_panel=control_panel,
            generated_at=generated_at,
            signal=signal,
        )
        return WorkspaceSignalSnapshot(
            generated_at=generated_at,
            signal=signal,
            roots=roots,
            root_details=root_details,
            market_snapshot=market_snapshot,
            market_availability=market_availability,
            related_signals=related_signals,
            evaluation=evaluation,
            control_panel=control_panel,
            trust_ribbon=self._build_trust_ribbon(control_panel=control_panel, admin_health=admin_health),
            system_confidence=self._build_system_confidence(
                control_panel=control_panel,
                admin_health=admin_health,
                evaluation=evaluation,
                active_signals=related_signals,
            ),
            visual=self._build_signal_visual(signal=signal, root_details=root_details),
            signal_diff=self._build_signal_change_summary(signal),
            confidence_decomposition=self._build_confidence_decomposition(signal, root_details=root_details),
            decision_log=self._build_decision_timeline(signal),
            similar_setups=self._build_similar_setups(signal),
        )

    def build_journal_snapshot(
        self,
        *,
        root: str | None = None,
        status: SignalStatus | None = None,
        kind: JournalEntryKind | None = None,
        signal_id: str | None = None,
        tag: str | None = None,
        limit: int = 120,
    ) -> JournalWorkspaceSnapshot:
        roots = self.contract_service.list_roots()
        related_signals = self._list_signals(root=root, status=status, limit=max(20, min(limit, 120)))
        entries: list[JournalWorkspaceEntry] = []
        decision_log: list[JournalDecisionLogItem] = []

        # Materialize journal across the current signal universe. This keeps the UX stable even on a fresh DB.
        for signal in related_signals:
            detail = self.signal_service.get_signal(signal.signal_id)
            if detail is None:
                detail = self._materialize_signal_detail(signal.signal_id)
            if detail is None:
                continue
            if signal_id is None or detail.signal_id == signal_id:
                decision_log.append(self._build_decision_log_item(detail))
            for entry in detail.journal_entries:
                if kind is not None and entry.kind != kind:
                    continue
                entries.append(JournalWorkspaceEntry(entry=entry, signal=signal))

        decision_log.sort(key=lambda item: item.updated_at, reverse=True)
        entries.sort(key=lambda item: item.entry.created_at, reverse=True)
        if signal_id is not None:
            entries = [item for item in entries if item.signal.signal_id == signal_id]
            related_signals = [item for item in related_signals if item.signal_id == signal_id] or related_signals
        tag_counts = self._journal_tag_counts(entries)
        selected_tag = (tag or "").strip() or None
        if selected_tag is not None:
            entries = [
                item
                for item in entries
                if selected_tag in {candidate.strip() for candidate in item.entry.tags}
            ]
        if selected_tag is not None:
            signal_ids_with_tag = {item.signal.signal_id for item in entries}
            decision_log = [item for item in decision_log if item.signal.signal_id in signal_ids_with_tag]
            related_signals = [item for item in related_signals if item.signal_id in signal_ids_with_tag]

        selected_signal_id = signal_id
        if selected_signal_id is None and entries:
            selected_signal_id = entries[0].signal.signal_id
        if selected_signal_id is None and decision_log:
            selected_signal_id = decision_log[0].signal.signal_id

        return JournalWorkspaceSnapshot(
            generated_at=datetime.now(UTC),
            roots=roots,
            selected_root=root,
            selected_status=status,
            selected_kind=kind,
            selected_signal_id=selected_signal_id,
            selected_tag=selected_tag,
            decision_log=decision_log[: min(limit, 12)],
            entries=entries[:limit],
            related_signals=related_signals[:12],
            total_entries=len(entries),
            thesis_entries=sum(1 for item in entries if item.entry.kind == JournalEntryKind.THESIS),
            risk_entries=sum(1 for item in entries if item.entry.kind == JournalEntryKind.RISK_NOTE),
            post_mortems=sum(1 for item in entries if item.entry.kind == JournalEntryKind.POST_MORTEM),
            note_templates=self._note_templates(),
            tag_suggestions=self._tag_suggestions(),
            tag_counts=tag_counts,
        )

    def _journal_tag_counts(self, entries: list[JournalWorkspaceEntry]) -> list[JournalTagSummary]:
        buckets: dict[str, dict[str, set[str] | int]] = {}
        for item in entries:
            for raw_tag in item.entry.tags:
                tag = raw_tag.strip()
                if not tag:
                    continue
                bucket = buckets.setdefault(tag, {"count": 0, "roots": set(), "kinds": set()})
                bucket["count"] = int(bucket["count"]) + 1
                roots = bucket["roots"]
                kinds = bucket["kinds"]
                if isinstance(roots, set):
                    roots.add(item.signal.root)
                if isinstance(kinds, set):
                    kinds.add(item.entry.kind.value)
        return [
            JournalTagSummary(
                tag=tag,
                count=int(data["count"]),
                roots=sorted(data["roots"]) if isinstance(data["roots"], set) else [],
                kinds=sorted(data["kinds"]) if isinstance(data["kinds"], set) else [],
            )
            for tag, data in sorted(buckets.items(), key=lambda pair: (-int(pair[1]["count"]), pair[0]))
        ]

    def add_watchlist_entry(self, *, root_code: str, signal_id: str | None = None, note: str | None = None) -> list[WatchlistEntry]:
        effective_root = root_code
        if signal_id is not None:
            signal = self.signal_service.get_signal(signal_id)
            if signal is not None:
                effective_root = signal.root
        watch_key = f"default:{effective_root}:{signal_id or 'root'}"
        self.repository.upsert_workspace_watch(
            watch_key=watch_key,
            profile_id="default",
            root_code=effective_root,
            signal_id=signal_id,
            note=note,
            updated_at=datetime.now(UTC),
        )
        return self._build_watchlist()

    def list_watchlist_entries(
        self,
        *,
        review_state: str | None = None,
        root_code: str | None = None,
        linked: str | None = None,
    ) -> list[WatchlistEntry]:
        return self._filter_watchlist(
            self._build_watchlist(),
            review_state=review_state,
            root_code=root_code,
            linked=linked,
        )

    def remove_watchlist_entry(self, watch_key: str) -> list[WatchlistEntry]:
        self.repository.delete_workspace_watch(watch_key=watch_key, profile_id="default")
        return self._build_watchlist()

    def mark_watchlist_entry_reviewed(self, watch_key: str) -> list[WatchlistEntry]:
        watches = self.repository.list_workspace_watches(profile_id="default")
        row = next((item for item in watches if item.watch_key == watch_key), None)
        if row is None:
            return self._build_watchlist()
        self.repository.upsert_workspace_watch(
            watch_key=row.watch_key,
            profile_id=row.profile_id,
            root_code=row.root_code,
            signal_id=row.signal_id,
            note=row.note,
            updated_at=datetime.now(UTC),
        )
        return self._build_watchlist()

    def build_horizon_comparison_snapshot(self, *, root: str) -> HorizonComparisonSnapshot | None:
        return self._build_horizon_comparison(selected_root=root, root_details=self.contract_service.get_root_deep_dive(root))

    def build_root_market_snapshot(self, *, root: str) -> InstrumentMarketSnapshot | None:
        generated_at = datetime.now(UTC)
        root_details = self.contract_service.get_root_deep_dive(root)
        if root_details is None:
            return None
        control_panel = self._build_control_panel(
            generated_at=generated_at,
            root_details=root_details,
            admin_health=self.observability_service.admin_health(),
        )
        market_signal = self._resolve_market_signal_for_root(
            root=root_details.root.root_code,
            root_details=root_details,
            preferred=None,
        )
        return self._build_instrument_market_snapshot(
            root_details=root_details,
            control_panel=control_panel,
            generated_at=generated_at,
            signal=market_signal,
        )

    def _resolve_market_signal_for_root(
        self,
        *,
        root: str,
        root_details,
        preferred: FinalSignalCard | FinalSignalDetail | None,
    ) -> FinalSignalCard | FinalSignalDetail | None:
        if preferred is not None and preferred.direction_final.value != "no_edge":
            return preferred
        if root_details is None:
            return preferred

        active_signals = self._list_signals(
            root=root,
            status=SignalStatus.ACTIVE,
            limit=12,
            seed_root_details=root_details,
        )
        directional = [item for item in active_signals if item.direction_final.value != "no_edge"]
        if not directional:
            fallback = self._select_market_signal(root_details=root_details, signal=None)
            if fallback is not None and fallback.direction_final.value != "no_edge":
                return fallback
            return preferred

        directional.sort(
            key=lambda item: (item.priority_score, item.confidence_final, item.generated_at),
            reverse=True,
        )
        selected = directional[0]
        return self.signal_service.get_signal(selected.signal_id) or selected

    def _select_market_signal(
        self,
        *,
        root_details,
        signal: FinalSignalCard | FinalSignalDetail | None,
    ) -> FinalSignalCard | FinalSignalDetail | None:
        if signal is not None:
            return signal
        if not root_details.active_signals:
            return None
        return max(
            root_details.active_signals,
            key=lambda item: (item.generated_at, item.confidence_final, item.priority_score),
        )

    def build_signal_diff(self, *, signal_id: str) -> SignalChangeSummary | None:
        signal = self._materialize_signal_detail(signal_id)
        return self._build_signal_change_summary(signal)

    def build_decision_log(self, *, signal_id: str) -> list[DecisionTimelineItem]:
        signal = self._materialize_signal_detail(signal_id)
        return self._build_decision_timeline(signal)

    def _build_decision_log_item(self, signal: FinalSignalDetail) -> JournalDecisionLogItem:
        entries = sorted(signal.journal_entries, key=lambda item: item.created_at, reverse=True)
        latest_entry = entries[0] if entries else None
        latest_thesis = next((item for item in entries if item.kind == JournalEntryKind.THESIS), None)
        latest_risk = next((item for item in entries if item.kind == JournalEntryKind.RISK_NOTE), None)
        latest_execution = next((item for item in entries if item.kind == JournalEntryKind.EXECUTION_NOTE), None)

        decision_summary = (
            latest_execution.note
            if latest_execution is not None
            else latest_thesis.note
            if latest_thesis is not None
            else signal.summary
        )
        why_now = signal.drivers[:3] or [signal.summary]
        next_watch = (
            signal.invalidation_conditions[:3]
            or ([latest_risk.note] if latest_risk is not None else [])
            or signal.objections[:3]
            or ["Capture what would invalidate or weaken this setup next."]
        )
        updated_at = latest_entry.created_at if latest_entry is not None else signal.generated_at

        return JournalDecisionLogItem(
            signal=FinalSignalCard.model_validate(signal.model_dump()),
            updated_at=updated_at,
            latest_entry=latest_entry,
            decision_summary=decision_summary,
            why_now=why_now,
            next_watch=next_watch,
        )

    def _list_signals(
        self,
        *,
        root: str | None = None,
        status: SignalStatus | None = None,
        limit: int,
        seed_root_details=None,
    ) -> list[FinalSignalCard]:
        rows = self.signal_service.list_signals(root=root, status=status, limit=limit)
        if rows:
            return rows

        if seed_root_details is not None:
            self.signal_service.build_signals_for_root(seed_root_details)
            rows = self.signal_service.list_signals(root=root, status=status, limit=limit)
            if rows:
                return rows

        built: list[FinalSignalCard] = []
        for item in self.contract_service.list_roots():
            deep_dive = seed_root_details if seed_root_details is not None and item.root_code == root else self.contract_service.get_root_deep_dive(item.root_code)
            if deep_dive is None:
                continue
            built.extend(FinalSignalCard.model_validate(signal.model_dump()) for signal in self.signal_service.build_signals_for_root(deep_dive))

        filtered = [
            item
            for item in built
            if (not root or item.root == root)
            and (not status or item.status == status)
        ]
        filtered.sort(key=lambda item: (item.generated_at, item.priority_score), reverse=True)
        return filtered[:limit]

    def _quality_pair(self, provider_a: str, provider_b: str) -> DashboardQualityPair:
        latest = self.quality_repository.get_latest_pair(provider_a=provider_a, provider_b=provider_b)
        return DashboardQualityPair(
            provider_a=provider_a,
            provider_b=provider_b,
            latest_contract=latest.contract if latest is not None else None,
            latest_at=latest.created_at if latest is not None else None,
            contracts_count=self.quality_repository.count_distinct_contracts_pair(
                provider_a=provider_a,
                provider_b=provider_b,
            ),
            mismatch_rate_overlap=(
                round(float(latest.mismatch_rate_overlap), 4) if latest is not None else None
            ),
        )

    def _build_control_panel(self, *, generated_at: datetime, root_details, admin_health) -> RuntimeControlPanel:
        feeds = self._build_market_data_feeds(
            generated_at=generated_at,
            root_details=root_details,
            admin_health=admin_health,
        )
        data_mode, data_mode_detail = self._derive_data_mode(feeds)
        latest_market_data_at = max(
            (item.last_update_at for item in feeds if item.last_update_at is not None),
            default=None,
        )
        reference_sync = self._build_reference_sync_status(generated_at=generated_at)
        return RuntimeControlPanel(
            generated_at=generated_at,
            llm_owner="OpenAI",
            llm_product="ChatGPT",
            llm_model="gpt-5",
            data_mode=data_mode,
            data_mode_detail=data_mode_detail,
            model_roles=self._build_model_roles(),
            market_data_feeds=feeds,
            latest_market_data_at=latest_market_data_at,
            reference_sync=reference_sync,
        )

    def _build_reference_sync_status(self, *, generated_at: datetime) -> ReferenceSyncStatus:
        state = self.repository.get_reference_sync_state()
        refresh_interval = timedelta(hours=max(1, settings.moex_reference_auto_sync_interval_hours))
        if state is None:
            return ReferenceSyncStatus(
                source="bundled_fallback",
                owner="Repository",
                status="fallback",
                detail="Using bundled contract metadata until MOEX ISS sync succeeds.",
                last_sync_at=None,
            )

        synced_at = state.synced_at if state.synced_at.tzinfo is not None else state.synced_at.replace(tzinfo=UTC)
        age = generated_at - synced_at
        if state.source == "moex_iss":
            status = "fresh" if age <= refresh_interval else "stale"
            detail = (
                state.detail
                or (
                    "Reference metadata is synced from MOEX ISS."
                    if status == "fresh"
                    else "Last MOEX ISS sync is older than the target interval; using the latest saved snapshot."
                )
            )
            owner = "MOEX"
        else:
            status = "fallback"
            detail = state.detail or "Using bundled contract metadata until MOEX ISS sync succeeds."
            owner = "Repository"

        return ReferenceSyncStatus(
            source=state.source,
            owner=owner,
            status=status,
            detail=detail,
            last_sync_at=synced_at,
        )

    def _build_model_roles(self) -> list[ModelRoleAssignment]:
        return self.runtime_control_service.list_model_routes()

    def _build_market_data_feeds(self, *, generated_at: datetime, root_details, admin_health) -> list[MarketDataFeedStatus]:
        provider_order: list[str] = []
        if root_details is not None:
            provider_order.append(root_details.root.primary_provider)
            if root_details.root.secondary_provider:
                provider_order.append(root_details.root.secondary_provider)

        source_index = {item.provider: item for item in admin_health.source_health}
        if root_details is not None:
            source_index.update({item.provider: item for item in root_details.sources})

        root_sources = [
            source_index[provider]
            for provider in provider_order
            if provider in source_index
        ]

        feeds: list[MarketDataFeedStatus] = []
        for item in root_sources:
            feeds.append(
                MarketDataFeedStatus(
                    provider=item.provider,
                    owner=self._provider_owner(item.provider),
                    role=self._market_data_role_label(item.role),
                    status=item.status.value,
                    primary=bool(item.primary),
                    detail=item.detail,
                    freshness_seconds=item.freshness_seconds,
                    last_update_at=self._derive_last_update_at(
                        generated_at=generated_at,
                        freshness_seconds=item.freshness_seconds,
                    ),
                )
            )
        return feeds

    def _provider_owner(self, provider: str) -> str:
        owners = {
            "alor": "Alor Broker",
            "bcs": "BCS",
            "cbr": "Bank of Russia",
            "finam": "Finam",
            "moex": "MOEX",
            "tbank": "T-Bank",
        }
        return owners.get(provider, provider.upper())

    def _market_data_role_label(self, role: str) -> str:
        labels = {
            "broker_market_data": "Broker market-data API",
            "exchange_reference": "Exchange reference API",
            "macro_events": "Macro-event calendar",
            "secondary_market_data": "Secondary market-data API",
            "shadow_market_data": "Shadow market-data API",
        }
        return labels.get(role, role.replace("_", " "))

    def _derive_last_update_at(self, *, generated_at: datetime, freshness_seconds: int | None) -> datetime | None:
        if freshness_seconds is None:
            return None
        return generated_at - timedelta(seconds=max(0, freshness_seconds))

    def _derive_data_mode(self, feeds: list[MarketDataFeedStatus]) -> tuple[str, str]:
        policy = self.runtime_control_service.get_freshness_policy()
        if not feeds:
            return (
                "degraded_feed",
                "No market-data feeds are attached to this root yet.",
            )

        primary_feeds = [item for item in feeds if item.primary]
        if not primary_feeds:
            primary_feeds = feeds[:1]

        if not any(item.status == "ok" for item in primary_feeds):
            return (
                "degraded_feed",
                "Primary price source is degraded or unavailable.",
            )

        live_roles = {"broker_market_data", "secondary_market_data", "shadow_market_data"}
        has_live_feed = any(
            item.status == "ok"
            and item.role in live_roles
            and item.freshness_seconds is not None
            and item.freshness_seconds <= policy.fresh_max_seconds
            for item in feeds
        )
        if has_live_feed:
            return (
                "live",
                "At least one fresh market-data API is healthy for this root.",
            )

        return (
            "snapshot",
            "MOEX live charts are available; broker and shadow feeds are not fully active.",
        )

    def _build_watchlist(self, *, profile_id: str = "default") -> list[WatchlistEntry]:
        watches = self.repository.list_workspace_watches(profile_id=profile_id)
        signals = {
            item.signal_id: item
            for item in self._list_signals(limit=24)
        }
        now = datetime.now(UTC)
        return [
            WatchlistEntry(
                watch_key=row.watch_key,
                root_code=row.root_code,
                signal_id=row.signal_id,
                note=row.note,
                priority_rank=index,
                focus_reason=self._watchlist_focus_reason(row=row, signal=signals.get(row.signal_id)),
                last_reviewed_at=row.updated_at,
                review_state=self._watchlist_review_state(row=row, now=now),
                added_at=row.created_at,
                updated_at=row.updated_at,
                signal=signals.get(row.signal_id) if row.signal_id else None,
            )
            for index, row in enumerate(watches, start=1)
        ]

    def _filter_watchlist(
        self,
        items: list[WatchlistEntry],
        *,
        review_state: str | None = None,
        root_code: str | None = None,
        linked: str | None = None,
    ) -> list[WatchlistEntry]:
        normalized_review_state = (review_state or "all").strip().lower()
        raw_root = (root_code or "all").strip()
        normalized_root = raw_root.upper()
        normalized_linked = (linked or "all").strip().lower()
        filtered = items
        if normalized_review_state not in {"", "all"}:
            filtered = [item for item in filtered if item.review_state == normalized_review_state]
        if raw_root.lower() not in {"", "all"}:
            filtered = [item for item in filtered if item.root_code.upper() == normalized_root]
        if normalized_linked in {"signal", "signal_linked", "linked"}:
            filtered = [item for item in filtered if item.signal_id is not None]
        elif normalized_linked in {"root", "root_level"}:
            filtered = [item for item in filtered if item.signal_id is None]
        return filtered

    def _workspace_mode(self, *, focus_signal: FinalSignalDetail | None, watchlist: list[WatchlistEntry]) -> str:
        if focus_signal is not None:
            if focus_signal.workflow_state.value in {"ready", "escalate", "resolved"}:
                return "manage"
            return "focus"
        if watchlist:
            return "scan"
        return "scan"

    def _build_attention_inbox(
        self,
        *,
        active_signals: list[FinalSignalCard],
        selected_root: str,
        selected_signal_id: str | None,
        watchlist: list[WatchlistEntry],
        pulses: list[WorkspaceRootPulse],
        market_snapshot: InstrumentMarketSnapshot | None,
        focus_signal_diff: SignalChangeSummary | None,
    ) -> list[AttentionInboxItem]:
        watched_signal_ids = {item.signal_id for item in watchlist if item.signal_id}
        watched_root_codes = {item.root_code.upper() for item in watchlist}
        pulse_by_root = {item.root_code.upper(): item for item in pulses}
        selected_root_key = selected_root.upper()

        items: list[AttentionInboxItem] = []
        seen_signal_ids: set[str] = set()
        for signal in active_signals:
            if signal.signal_id in seen_signal_ids:
                continue
            seen_signal_ids.add(signal.signal_id)
            workflow_value = signal.workflow_state.value
            if workflow_value in {"ignored", "resolved"}:
                continue

            root_key = signal.root.upper()
            is_focus = signal.signal_id == selected_signal_id
            is_watched = signal.signal_id in watched_signal_ids or root_key in watched_root_codes
            pulse = pulse_by_root.get(root_key)
            market_status = "unknown"
            market_status_detail = "Open the root to inspect chart freshness before acting."
            if root_key == selected_root_key and market_snapshot is not None:
                market_status = market_snapshot.status
                market_status_detail = market_snapshot.status_detail
            elif root_key == selected_root_key:
                market_status = "hidden"
                market_status_detail = "Current price and charts are hidden until a traceable market-data snapshot is available."

            attention_score = self._attention_item_score(
                signal,
                is_focus=is_focus,
                is_watched=is_watched,
                market_status=market_status,
            )
            items.append(
                AttentionInboxItem(
                    item_key=f"signal:{signal.signal_id}",
                    item_type="signal",
                    root_code=signal.root,
                    signal_id=signal.signal_id,
                    title=f"{signal.root} {signal.horizon.value} {signal.direction_final.value}",
                    reason=self._attention_reason(
                        signal,
                        is_focus=is_focus,
                        is_watched=is_watched,
                        market_status=market_status,
                    ),
                    what_changed=self._attention_change_summary(
                        signal,
                        is_focus=is_focus,
                        focus_signal_diff=focus_signal_diff,
                    ),
                    next_step=self._attention_next_step(
                        signal,
                        is_watched=is_watched,
                        market_status=market_status,
                    ),
                    tone=self._attention_tone(signal, market_status=market_status),
                    priority_score=signal.priority_score,
                    attention_score=attention_score,
                    workflow_state=signal.workflow_state,
                    current_price=(
                        market_snapshot.current_price
                        if root_key == selected_root_key and market_snapshot is not None
                        else (pulse.current_price if pulse is not None else None)
                    ),
                    price_unit=(
                        market_snapshot.unit
                        if root_key == selected_root_key and market_snapshot is not None
                        else (pulse.price_unit if pulse is not None else None)
                    ),
                    market_status=market_status,
                    market_status_detail=market_status_detail,
                    href=f"/workspace?root={signal.root}&signal_id={signal.signal_id}",
                )
            )

        represented_roots = {item.root_code.upper() for item in items}
        for watch in watchlist:
            if watch.signal_id is not None:
                continue
            root_key = watch.root_code.upper()
            if root_key in represented_roots:
                continue
            pulse = pulse_by_root.get(root_key)
            review_due_bonus = 14.0 if watch.review_state == "review_due" else 0.0
            attention_score = round(max(0.0, min(100.0, 54.0 + review_due_bonus - watch.priority_rank)), 2)
            items.append(
                AttentionInboxItem(
                    item_key=f"watch:{watch.watch_key}",
                    item_type="root",
                    root_code=watch.root_code,
                    title=f"{watch.root_code} watchlist review",
                    reason=watch.focus_reason or "Root-level watch item needs a scheduled review.",
                    what_changed=(
                        pulse.headline
                        if pulse is not None
                        else "No active setup is attached yet; root remains in the personal queue."
                    ),
                    next_step="Open the root workspace, verify current price and 1D/1W/1M charts, then mark the queue item reviewed.",
                    tone="warning" if watch.review_state == "review_due" else "neutral",
                    priority_score=max(0, 100 - watch.priority_rank),
                    attention_score=attention_score,
                    current_price=pulse.current_price if pulse is not None else None,
                    price_unit=pulse.price_unit if pulse is not None else None,
                    market_status="unknown",
                    market_status_detail="Open the root to inspect chart freshness before acting.",
                    href=f"/workspace?root={watch.root_code}",
                )
            )

        return sorted(
            items,
            key=lambda item: (item.attention_score, item.priority_score),
            reverse=True,
        )[:5]

    def _attention_item_score(
        self,
        signal: FinalSignalCard,
        *,
        is_focus: bool,
        is_watched: bool,
        market_status: str,
    ) -> float:
        score = self._attention_score(signal) * 100.0
        if is_focus:
            score += 8.0
        if is_watched:
            score += 12.0
        if signal.workflow_state.value == "ready":
            score += 8.0
        elif signal.workflow_state.value == "escalate":
            score += 6.0
        if market_status in {"stale", "degraded", "hidden"}:
            score += 8.0
        return round(max(0.0, min(100.0, score)), 2)

    def _attention_reason(
        self,
        signal: FinalSignalCard,
        *,
        is_focus: bool,
        is_watched: bool,
        market_status: str,
    ) -> str:
        reasons: list[str] = []
        if is_focus:
            reasons.append("current focus signal")
        if is_watched:
            reasons.append("promoted to the daily queue")
        if signal.workflow_state.value in {"ready", "escalate", "validating"}:
            reasons.append(f"workflow is {signal.workflow_state.value}")
        if market_status in {"stale", "degraded", "hidden"}:
            reasons.append(f"market data is {market_status}")
        if not reasons:
            reasons.append("highest attention score in the active signal set")
        return "; ".join(reasons) + "."

    def _attention_change_summary(
        self,
        signal: FinalSignalCard,
        *,
        is_focus: bool,
        focus_signal_diff: SignalChangeSummary | None,
    ) -> str:
        if is_focus and focus_signal_diff is not None:
            return focus_signal_diff.summary
        return (
            f"{signal.horizon.value} {signal.direction_final.value}: "
            f"confidence {signal.confidence_final:.2f}, skeptic {signal.skeptic_score:.2f}, "
            f"freshness {signal.freshness_score:.2f}."
        )

    def _attention_next_step(
        self,
        signal: FinalSignalCard,
        *,
        is_watched: bool,
        market_status: str,
    ) -> str:
        if market_status in {"stale", "degraded", "hidden"}:
            return "Verify the current price and chart freshness before relying on this setup."
        if signal.workflow_state.value in {"ready", "escalate"}:
            return "Open the decision pack, compare 1D/1W/1M context, and journal the operator decision."
        if is_watched:
            return "Review the watchlist thesis and either keep, remove, or mark the item reviewed."
        return "Open the focus view and decide whether this setup belongs in the watchlist."

    def _attention_tone(self, signal: FinalSignalCard, *, market_status: str) -> str:
        if market_status in {"stale", "degraded", "hidden"}:
            return "warning"
        if signal.workflow_state.value == "ready":
            return "positive"
        if signal.workflow_state.value in {"escalate", "validating"}:
            return "warning"
        return "neutral"

    def _watchlist_focus_reason(self, *, row, signal: FinalSignalCard | None) -> str:
        note = (row.note or "").strip()
        if note:
            return note
        if signal is not None:
            return signal.summary
        return "Root-level watch item"

    def _watchlist_review_state(self, *, row, now: datetime) -> str:
        reviewed_at = row.updated_at
        if reviewed_at.tzinfo is None:
            reviewed_at = reviewed_at.replace(tzinfo=UTC)
        return "reviewed_today" if reviewed_at.date() == now.date() else "review_due"

    def _build_horizon_comparison(self, *, selected_root: str, root_details) -> HorizonComparisonSnapshot | None:
        related = self._list_signals(root=selected_root, limit=12, seed_root_details=root_details)
        if not related:
            return None
        items = sorted(
            related,
            key=lambda item: item.horizon.value,
        )
        return HorizonComparisonSnapshot(
            root=selected_root,
            items=[
                HorizonComparisonItem(
                    horizon=item.horizon.value,
                    direction=item.direction_final.value,
                    confidence=item.confidence_final,
                    skeptic_score=item.skeptic_score,
                    freshness_score=item.freshness_score,
                    attention_score=self._attention_score(item),
                    summary=item.summary,
                    workflow_state=item.workflow_state,
                )
                for item in items
            ],
        )

    def _build_trust_ribbon(self, *, control_panel: RuntimeControlPanel, admin_health) -> TrustRibbon:
        items = [
            TrustRibbonItem(
                label="Data mode",
                value=control_panel.data_mode,
                tone=self._tone_from_status(control_panel.data_mode),
                detail=control_panel.data_mode_detail,
            ),
            TrustRibbonItem(
                label="Reference",
                value=control_panel.reference_sync.status,
                tone=self._tone_from_status(control_panel.reference_sync.status),
                detail=control_panel.reference_sync.detail,
            ),
            TrustRibbonItem(
                label="Platform",
                value=admin_health.status,
                tone=self._tone_from_status(admin_health.status),
                detail="Database, scheduler, and source posture.",
            ),
        ]
        headline = "Trader trust is healthy." if all(item.tone == "positive" for item in items) else "Review runtime trust before acting."
        tone = "positive" if all(item.tone == "positive" for item in items) else "warning"
        return TrustRibbon(headline=headline, tone=tone, items=items)

    def _build_system_confidence(
        self,
        *,
        control_panel: RuntimeControlPanel,
        admin_health,
        evaluation: EvaluationSummary,
        active_signals: list[FinalSignalCard],
    ) -> SystemConfidencePanel:
        score = 100
        drivers = []
        if control_panel.data_mode == "snapshot":
            score -= 18
            drivers.append("Live feeds are not fully fresh.")
        elif control_panel.data_mode == "degraded_feed":
            score -= 34
            drivers.append("Primary feed posture is degraded.")
        else:
            drivers.append("A healthy live feed is present.")
        if control_panel.reference_sync.status == "stale":
            score -= 10
            drivers.append("Contract reference sync is aging.")
        elif control_panel.reference_sync.status == "fallback":
            score -= 18
            drivers.append("Bundled fallback reference snapshot is active.")
        if admin_health.status != "ok":
            score -= 12
            drivers.append("Operational health is not fully green.")
        if not active_signals:
            score -= 6
            drivers.append("No active setups are currently available.")
        if evaluation.resolved_signals > 0:
            drivers.append(f"{evaluation.resolved_signals} resolved signals support calibration.")
        score = max(20, min(99, score))
        tone = "positive" if score >= 80 else "warning" if score >= 60 else "negative"
        label = "high" if score >= 80 else "medium" if score >= 60 else "fragile"
        detail = "Combined view of feed freshness, reference sync, health, and evaluation coverage."
        return SystemConfidencePanel(score=score, label=label, tone=tone, detail=detail, drivers=drivers[:4])

    def _build_signal_change_summary(self, signal: FinalSignalDetail | None) -> SignalChangeSummary | None:
        if signal is None:
            return None
        versions = self.repository.list_signal_versions(
            root=signal.root,
            contract=signal.contract,
            horizon=signal.horizon.value,
            limit=4,
        )
        previous = next((item for item in versions if item.signal_id != signal.signal_id), None)
        if previous is None:
            return SignalChangeSummary(signal_id=signal.signal_id, summary="No earlier recalculation is available yet.")
        previous_drivers = self._split_blob(previous.drivers_blob)
        previous_invalidations = self._split_blob(previous.invalidation_conditions_blob)
        previous_sources = self._split_blob(previous.data_sources_blob)
        drivers_added, drivers_removed = self._diff_lists(signal.drivers, previous_drivers)
        invalidations_added, invalidations_removed = self._diff_lists(signal.invalidation_conditions, previous_invalidations)
        sources_added, sources_removed = self._diff_lists(signal.data_sources, previous_sources)
        confidence_delta = round(signal.confidence_final - float(previous.confidence_final), 4)
        skeptic_delta = round(signal.skeptic_score - float(previous.skeptic_score), 4)
        freshness_delta = round(signal.freshness_score - float(previous.freshness_score or 0), 4)
        changed = any(
            abs(value) >= 0.0001
            for value in (
                signal.probability_up - float(previous.probability_up),
                signal.probability_down - float(previous.probability_down),
                confidence_delta,
                skeptic_delta,
                freshness_delta,
            )
        ) or any((drivers_added, drivers_removed, invalidations_added, invalidations_removed, sources_added, sources_removed))
        summary = (
            "Signal changed since the last recalculation."
            if changed
            else "Signal is materially unchanged versus the last recalculation."
        )
        return SignalChangeSummary(
            signal_id=signal.signal_id,
            previous_signal_id=previous.signal_id,
            changed=changed,
            summary=summary,
            probability_up_delta=round(signal.probability_up - float(previous.probability_up), 4),
            probability_down_delta=round(signal.probability_down - float(previous.probability_down), 4),
            confidence_delta=confidence_delta,
            skeptic_delta=skeptic_delta,
            freshness_delta=freshness_delta,
            drivers_added=drivers_added,
            drivers_removed=drivers_removed,
            invalidations_added=invalidations_added,
            invalidations_removed=invalidations_removed,
            data_sources_added=sources_added,
            data_sources_removed=sources_removed,
        )

    def _build_confidence_decomposition(
        self,
        signal: FinalSignalDetail | None,
        *,
        root_details,
    ) -> ConfidenceDecomposition | None:
        if signal is None:
            return None
        factors = [
            ConfidenceFactor(label="Final confidence", value=signal.confidence_final, tone="positive" if signal.confidence_final >= 0.6 else "warning"),
            ConfidenceFactor(label="Skeptic support", value=signal.skeptic_score, tone="positive" if signal.skeptic_score >= 0.6 else "warning"),
            ConfidenceFactor(label="Freshness", value=signal.freshness_score, tone="positive" if signal.freshness_score >= 0.75 else "warning"),
        ]
        if root_details is not None:
            roll_penalty = max(0.0, min(1.0, 1.0 - root_details.continuous_series.next_contract_share))
            factors.append(
                ConfidenceFactor(
                    label="Roll posture",
                    value=round(roll_penalty, 4),
                    tone="positive" if roll_penalty >= 0.7 else "warning",
                    detail=f"Next-contract share {root_details.continuous_series.next_contract_share:.0%}.",
                )
            )
        headline = "Conviction comes from confidence, skeptic support, freshness, and roll posture."
        return ConfidenceDecomposition(headline=headline, factors=factors)

    def _build_decision_timeline(self, signal: FinalSignalDetail | None) -> list[DecisionTimelineItem]:
        if signal is None:
            return []
        timeline = [
            DecisionTimelineItem(
                at=signal.generated_at,
                kind="signal",
                title="Signal published",
                detail=signal.summary,
                tone="positive" if signal.direction_final.value != "no_edge" else "neutral",
            ),
            DecisionTimelineItem(
                at=signal.generated_at,
                kind="workflow",
                title="Workflow state",
                detail=f"Marked as {signal.workflow_state.value}.",
                tone=self._workflow_tone(signal.workflow_state.value),
            ),
        ]
        for entry in signal.journal_entries:
            timeline.append(
                DecisionTimelineItem(
                    at=entry.created_at,
                    kind=entry.kind.value,
                    title=entry.title,
                    detail=entry.note,
                    tone="warning" if entry.kind == JournalEntryKind.RISK_NOTE else "neutral",
                    tags=entry.tags,
                )
            )
        if signal.resolution is not None:
            timeline.append(
                DecisionTimelineItem(
                    at=signal.resolution.resolved_at,
                    kind="resolution",
                    title=f"Resolved as {signal.resolution.outcome.value}",
                    detail=signal.resolution.resolution_note,
                    tone="positive" if signal.resolution.outcome.value == "win" else "negative",
                )
            )
        timeline.sort(key=lambda item: self._coerce_utc(item.at), reverse=True)
        return timeline

    def _build_similar_setups(self, signal: FinalSignalDetail) -> list[HistoricalSetup]:
        rows = self.repository.list_similar_resolutions(root=signal.root, horizon=signal.horizon.value, limit=5)
        results: list[HistoricalSetup] = []
        for row in rows:
            similarity = max(0.1, 1.0 - abs(float(row.realized_return_bps)) / 1000.0)
            results.append(
                HistoricalSetup(
                    signal_id=row.signal_id,
                    outcome=row.outcome,
                    realized_return_bps=float(row.realized_return_bps),
                    resolved_at=row.resolved_at,
                    note=row.post_mortem_summary or row.resolution_note,
                    similarity_score=round(similarity, 4),
                )
            )
        return results

    def _build_review_bundle(self, *, roots) -> ReviewBundle:
        signals = self._list_signals(limit=64)
        watched = self._build_watchlist()
        watched_root_codes = sorted({item.root_code for item in watched})
        review_due = sum(1 for item in watched if item.review_state == "review_due")
        reviewed_today = sum(1 for item in watched if item.review_state == "reviewed_today")
        ignored = sum(1 for item in signals if item.workflow_state.value == "ignored")
        resolved = self.repository.count_signals(status="resolved")
        journal_entries = self.repository.count_journal_entries()
        outcomes = self._review_outcome_summary()
        next_actions = self._review_next_actions(
            watched=watched,
            review_due=review_due,
            ignored=ignored,
            resolved=resolved,
            journal_entries=journal_entries,
        )
        return ReviewBundle(
            watchlist_items=len(watched),
            watched_roots=len({item.root_code for item in watched}),
            watched_root_codes=watched_root_codes,
            review_due_items=review_due,
            reviewed_today_items=reviewed_today,
            decisions_logged=journal_entries,
            ignored_signals=ignored,
            resolved_signals=resolved,
            outcome_summary=outcomes,
            tag_suggestions=self._tag_suggestions(),
            next_review_actions=next_actions,
            highlights=[
                f"{len(watched)} watchlist items are being monitored.",
                f"{len(roots)} roots are available in the current universe.",
                f"{review_due} watchlist items still need review today.",
            ],
        )

    def _review_outcome_summary(self) -> list[str]:
        rows = self.repository.list_signal_resolutions(limit=5)
        if not rows:
            return ["No resolved outcomes yet; post-resolution review will appear here after signals are closed."]
        return [
            f"{row.root_code} {row.horizon}: {row.outcome} ({float(row.realized_return_bps):+.1f} bps)"
            for row in rows
        ]

    def _review_next_actions(
        self,
        *,
        watched: list[WatchlistEntry],
        review_due: int,
        ignored: int,
        resolved: int,
        journal_entries: int,
    ) -> list[str]:
        actions: list[str] = []
        if review_due:
            actions.append(f"Review {review_due} queued watchlist item(s) before the close.")
        elif watched:
            actions.append("All watchlist items are reviewed today; capture any changed thesis or risk.")
        else:
            actions.append("Promote at least one root or signal into watchlist before end-of-day review.")
        if journal_entries == 0:
            actions.append("Add at least one thesis or risk note so tomorrow starts with context.")
        if ignored:
            actions.append(f"Check {ignored} ignored signal(s) for false urgency, late timing, or data issues.")
        if resolved:
            actions.append(f"Use {resolved} resolved signal(s) as calibration anchors for confidence quality.")
        else:
            actions.append("No resolved outcomes yet; keep post-mortem slots ready for the first closed setup.")
        return actions

    def _note_templates(self) -> list[dict[str, str]]:
        return [
            {"kind": "thesis", "title": "Thesis update", "prompt": "What changed, why it matters, and what supports the setup now?"},
            {"kind": "invalidation_breach", "title": "Invalidation breach", "prompt": "What level or condition failed, and how does that change the plan?"},
            {"kind": "execution_note", "title": "Execution observation", "prompt": "What did the market do around the decision window?"},
            {"kind": "post_mortem", "title": "Post-mortem", "prompt": "What worked, what failed, and what will you repeat or avoid?"},
            {"kind": "data_anomaly", "title": "Data anomaly", "prompt": "What looked stale, missing, or contradictory in the inputs?"},
        ]

    def _tag_suggestions(self) -> list[str]:
        return ["false urgency", "late", "great context", "data issue", "good skeptic catch"]

    def _attention_score(self, signal: FinalSignalCard) -> float:
        score = signal.confidence_final * 0.45 + signal.skeptic_score * 0.2 + signal.freshness_score * 0.15 + min(signal.priority_score / 100.0, 1.0) * 0.2
        if signal.workflow_state.value == "ready":
            score += 0.08
        if signal.workflow_state.value == "escalate":
            score += 0.05
        return round(min(1.0, score), 4)

    def _tone_from_status(self, status: str) -> str:
        if status in {"live", "fresh", "ok", "high"}:
            return "positive"
        if status in {"snapshot", "stale", "degraded", "medium", "warning"}:
            return "warning"
        return "negative"

    def _workflow_tone(self, workflow_state: str) -> str:
        if workflow_state in {"ready", "resolved"}:
            return "positive"
        if workflow_state in {"escalate", "validating"}:
            return "warning"
        if workflow_state == "ignored":
            return "negative"
        return "neutral"

    def _split_blob(self, value: str | None) -> list[str]:
        if not value:
            return []
        return [item for item in value.split("\n") if item]

    def _diff_lists(self, current: list[str], previous: list[str]) -> tuple[list[str], list[str]]:
        current_set = set(current)
        previous_set = set(previous)
        return (
            [item for item in current if item not in previous_set],
            [item for item in previous if item not in current_set],
        )

    def _resolve_focus_signal(
        self,
        *,
        selected_root: str,
        signal_id: str | None,
        signal_lane: list[FinalSignalCard],
        root_details,
    ) -> FinalSignalDetail | None:
        if signal_id:
            detail = self.signal_service.get_signal(signal_id)
            if detail is not None:
                return detail

        preferred_id = signal_lane[0].signal_id if signal_lane else None
        if preferred_id is not None:
            detail = self.signal_service.get_signal(preferred_id)
            if detail is not None:
                return detail

        if root_details is not None:
            self.signal_service.build_signals_for_root(root_details)
            if signal_id:
                detail = self.signal_service.get_signal(signal_id)
                if detail is not None:
                    return detail
            if preferred_id is not None:
                detail = self.signal_service.get_signal(preferred_id)
                if detail is not None:
                    return detail

        fallback = self._list_signals(root=selected_root, limit=1, seed_root_details=root_details)
        if not fallback:
            return None
        return self.signal_service.get_signal(fallback[0].signal_id)

    def _materialize_signal_detail(self, signal_id: str) -> FinalSignalDetail | None:
        detail = self.signal_service.get_signal(signal_id)
        if detail is not None:
            return detail

        for item in self.contract_service.list_roots():
            deep_dive = self.contract_service.get_root_deep_dive(item.root_code)
            if deep_dive is None:
                continue
            built = self.signal_service.build_signals_for_root(deep_dive)
            detail = self.signal_service.get_signal(signal_id)
            if detail is not None:
                return detail
            fallback = next((signal for signal in built if signal.signal_id == signal_id), None)
            if fallback is not None:
                return fallback
        return None

    def _build_pulses(
        self,
        *,
        roots,
        active_signals: list[FinalSignalCard],
        selected_root: str,
        generated_at: datetime,
    ) -> list[WorkspaceRootPulse]:
        pulses: list[WorkspaceRootPulse] = []
        for item in roots:
            deep_dive = self.contract_service.get_root_deep_dive(item.root_code)
            session_type = deep_dive.session.session_type if deep_dive is not None else None
            next_share = deep_dive.continuous_series.next_contract_share if deep_dive is not None else 0.0
            root_signals = [signal for signal in active_signals if signal.root == item.root_code]
            top_signal = root_signals[0] if root_signals else None
            live_quote = self._live_quote_snapshot(
                root_code=item.root_code,
                contract=item.active_contract,
                primary_provider=item.primary_provider,
                secondary_provider=item.secondary_provider,
                unit_hint=self._instrument_price_unit(item.root_code),
                generated_at=generated_at,
            )
            tone = "positive" if item.root_code == selected_root else "warning" if root_signals else "neutral"
            headline = top_signal.summary if top_signal is not None else "No active setup yet; keep root on watch."
            pulses.append(
                WorkspaceRootPulse(
                    root_code=item.root_code,
                    base_asset=item.base_asset,
                    session_type=session_type,
                    active_contract=item.active_contract,
                    active_signals=len(root_signals),
                    next_contract_share=next_share,
                    liquidity_rank=item.liquidity_rank,
                    best_direction=top_signal.direction_final if top_signal is not None else None,
                    current_price=live_quote.current_price if live_quote is not None else None,
                    price_change_abs=live_quote.price_change_abs if live_quote is not None else None,
                    price_change_pct=live_quote.price_change_pct if live_quote is not None else None,
                    price_unit=live_quote.unit if live_quote is not None else self._instrument_price_unit(item.root_code),
                    headline=headline,
                    tone=tone,
                )
            )
        return pulses

    def _build_instrument_market_snapshot(
        self,
        *,
        root_details,
        control_panel,
        generated_at: datetime,
        signal: FinalSignalCard | FinalSignalDetail | None,
    ) -> InstrumentMarketSnapshot | None:
        snapshot, _availability = self._build_instrument_market_state(
            root_details=root_details,
            control_panel=control_panel,
            generated_at=generated_at,
            signal=signal,
        )
        return snapshot

    def _build_instrument_market_state(
        self,
        *,
        root_details,
        control_panel,
        generated_at: datetime,
        signal: FinalSignalCard | FinalSignalDetail | None,
    ) -> tuple[InstrumentMarketSnapshot | None, MarketAvailabilitySnapshot | None]:
        if root_details is None:
            return None, MarketAvailabilitySnapshot(
                status="hidden",
                reason_code="no_root_details",
                detail="No selected root details are available, so market charts stay hidden.",
                checked_at=generated_at,
            )

        effective_signal = self._select_market_signal(root_details=root_details, signal=signal)
        live_snapshot = self.market_data_service.get_market_snapshot(
            root_code=root_details.root.root_code,
            contract=root_details.continuous_series.active_contract,
            providers=self._market_data_providers(
                primary_provider=root_details.root.primary_provider,
                secondary_provider=root_details.root.secondary_provider,
            ),
            unit_hint=self._instrument_price_unit(root_details.root.root_code),
            now=generated_at,
        )
        if live_snapshot is None:
            return None, self._build_market_availability(
                root_details=root_details,
                generated_at=generated_at,
                reason_code="no_traceable_snapshot",
                detail="No traceable quote plus candle snapshot was returned by the configured market-data providers.",
            )

        daily = self._build_chart_series_from_bars(
            label="1D",
            bars=live_snapshot.daily_bars,
            max_points=12,
            label_kind="hour",
        )
        weekly = self._build_chart_series_from_bars(
            label="1W",
            bars=live_snapshot.weekly_bars,
            max_points=7,
            label_kind="date",
        )
        monthly = self._build_chart_series_from_bars(
            label="1M",
            bars=live_snapshot.monthly_bars,
            max_points=6,
            label_kind="date",
        )
        missing_timeframes = [
            label
            for label, series in (("1D", daily), ("1W", weekly), ("1M", monthly))
            if series is None
        ]
        if missing_timeframes:
            return None, self._build_market_availability(
                root_details=root_details,
                generated_at=generated_at,
                reason_code=self._market_missing_timeframes_reason_code(
                    root_details=root_details,
                    missing_timeframes=missing_timeframes,
                ),
                detail=(
                    "Provider returned a live quote, but did not return traceable candle bars for "
                    f"{', '.join(missing_timeframes)}. Charts stay hidden instead of using approximate data."
                ),
                missing_timeframes=missing_timeframes,
            )
        signals_by_horizon = self._market_signals_by_horizon(
            root_details=root_details,
            preferred=effective_signal,
        )
        daily = self._with_timeframe_market_overlays(
            daily,
            signal=self._select_timeframe_market_signal(label="1D", signals_by_horizon=signals_by_horizon),
        )
        weekly = self._with_timeframe_market_overlays(
            weekly,
            signal=self._select_timeframe_market_signal(label="1W", signals_by_horizon=signals_by_horizon),
        )
        monthly = self._with_timeframe_market_overlays(
            monthly,
            signal=self._select_timeframe_market_signal(label="1M", signals_by_horizon=signals_by_horizon),
        )
        return InstrumentMarketSnapshot(
            root_code=root_details.root.root_code,
            contract=root_details.continuous_series.active_contract,
            base_asset=root_details.root.base_asset,
            unit=live_snapshot.unit or self._instrument_price_unit(root_details.root.root_code),
            current_price=live_snapshot.quote.current_price,
            price_change_abs=(
                live_snapshot.quote.price_change_abs
                if live_snapshot.quote.price_change_abs is not None
                else daily.change_abs
            ),
            price_change_pct=(
                live_snapshot.quote.price_change_pct
                if live_snapshot.quote.price_change_pct is not None
                else daily.change_pct
            ),
            price_source=f"{live_snapshot.provider} live",
            status=live_snapshot.status or "fresh",
            status_detail=live_snapshot.detail,
            as_of=live_snapshot.as_of,
            daily=daily,
            weekly=weekly,
            monthly=monthly,
        ), None

    def _market_missing_timeframes_reason_code(self, *, root_details, missing_timeframes: list[str]) -> str:
        session_type = getattr(getattr(root_details, "session", None), "session_type", None)
        if session_type == SessionType.HALTED:
            return "outside_exchange_session"
        if session_type == SessionType.CLEARING:
            return "clearing_window"
        if session_type == SessionType.WEEKEND:
            return "weekend_session_no_candles"
        if "1D" in missing_timeframes:
            return "intraday_candles_unavailable"
        return "missing_candles"

    def _build_market_availability(
        self,
        *,
        root_details,
        generated_at: datetime,
        reason_code: str,
        detail: str,
        missing_timeframes: list[str] | None = None,
    ) -> MarketAvailabilitySnapshot:
        session = getattr(root_details, "session", None)
        session_type = getattr(session, "session_type", None)
        if session_type == SessionType.HALTED and "outside" not in detail.lower():
            detail = (
                "The selected root is outside the local MOEX/FORTS trading window; "
                "charts stay hidden until a traceable session snapshot is available."
            )
        elif session_type == SessionType.CLEARING and "clearing" not in detail.lower():
            detail = (
                "The selected root is in a local clearing window; charts stay hidden until "
                "a traceable post-clearing candle snapshot is available."
            )
        return MarketAvailabilitySnapshot(
            status="hidden",
            reason_code=reason_code,
            detail=detail,
            checked_at=generated_at,
            session_type=session_type,
            session_start_at=getattr(session, "session_start_at", None),
            session_end_at=getattr(session, "session_end_at", None),
            rule_set=getattr(session, "effective_rule_set", None),
            missing_timeframes=list(missing_timeframes or []),
        )

    def _build_synthetic_instrument_market_snapshot(
        self,
        *,
        root_details,
        control_panel,
        generated_at: datetime,
        signal: FinalSignalCard | FinalSignalDetail | None,
    ) -> InstrumentMarketSnapshot:
        if root_details is None:
            raise ValueError("Root details are required for a synthetic market snapshot.")

        features = list(root_details.feature_snapshots)
        active_signal = self._select_market_signal(root_details=root_details, signal=signal)

        trend_bias = self._safe_average(item.trend_slope for item in features)
        volatility = self._safe_average(item.realized_volatility for item in features)
        return_score = self._safe_average(item.return_score for item in features)
        conviction = 0.0
        confidence = 0.5
        if active_signal is not None:
            conviction = float(active_signal.probability_up) - float(active_signal.probability_down)
            confidence = float(active_signal.confidence_final)
        roll_drag = float(root_details.continuous_series.next_contract_share) * 0.018
        base_price = self._instrument_price_baseline(root_details.root.root_code)
        current_price = base_price * (
            1
            + trend_bias * 0.14
            + return_score * 0.07
            + conviction * 0.08
            + (confidence - 0.5) * 0.05
            - roll_drag
        )
        current_price = round(max(base_price * 0.45, current_price), 2)

        daily = self._build_instrument_chart_series(
            label="1D",
            points_count=12,
            current_price=current_price,
            trend_bias=trend_bias,
            volatility=volatility,
            conviction=conviction,
            generated_at=generated_at,
            label_kind="hour",
            lookback_step=timedelta(minutes=30),
            amplitude_scale=0.38,
        )
        weekly = self._build_instrument_chart_series(
            label="1W",
            points_count=7,
            current_price=current_price,
            trend_bias=trend_bias,
            volatility=volatility,
            conviction=conviction,
            generated_at=generated_at,
            label_kind="weekday",
            lookback_step=timedelta(days=1),
            amplitude_scale=0.72,
        )
        monthly = self._build_instrument_chart_series(
            label="1M",
            points_count=6,
            current_price=current_price,
            trend_bias=trend_bias,
            volatility=volatility,
            conviction=conviction,
            generated_at=generated_at,
            label_kind="date",
            lookback_step=timedelta(days=5),
            amplitude_scale=1.08,
        )
        signals_by_horizon = self._market_signals_by_horizon(
            root_details=root_details,
            preferred=active_signal,
        )
        daily = self._with_timeframe_market_overlays(
            daily,
            signal=self._select_timeframe_market_signal(label="1D", signals_by_horizon=signals_by_horizon),
        )
        weekly = self._with_timeframe_market_overlays(
            weekly,
            signal=self._select_timeframe_market_signal(label="1W", signals_by_horizon=signals_by_horizon),
        )
        monthly = self._with_timeframe_market_overlays(
            monthly,
            signal=self._select_timeframe_market_signal(label="1M", signals_by_horizon=signals_by_horizon),
        )

        price_source = f"{root_details.root.primary_provider} snapshot proxy"
        status = "fresh"
        status_detail = None
        as_of = generated_at
        if control_panel is not None:
            primary_feed = next((item for item in control_panel.market_data_feeds if item.primary), None)
            if primary_feed is None and control_panel.market_data_feeds:
                primary_feed = control_panel.market_data_feeds[0]
            if primary_feed is not None:
                price_source = f"{primary_feed.provider} snapshot proxy"
                status = primary_feed.status
                status_detail = primary_feed.detail
                as_of = primary_feed.last_update_at or generated_at
            else:
                status = control_panel.data_mode
                status_detail = control_panel.data_mode_detail
                as_of = control_panel.latest_market_data_at or generated_at

        return InstrumentMarketSnapshot(
            root_code=root_details.root.root_code,
            contract=root_details.continuous_series.active_contract,
            base_asset=root_details.root.base_asset,
            unit=self._instrument_price_unit(root_details.root.root_code),
            current_price=daily.current_price,
            price_change_abs=daily.change_abs,
            price_change_pct=daily.change_pct,
            price_source=price_source,
            status=status,
            status_detail=status_detail,
            as_of=as_of,
            daily=daily,
            weekly=weekly,
            monthly=monthly,
        )

    def _build_chart_series_from_bars(
        self,
        *,
        label: str,
        bars: list[Bar],
        max_points: int,
        label_kind: str,
    ) -> InstrumentChartSeries | None:
        if not bars:
            return None

        sampled_bars = self._sample_bars(bars, max_points=max_points)
        points = [
            InstrumentChartPoint(
                label=self._instrument_chart_label(bar.end_at, kind=label_kind),
                value=round(bar.close, 2),
                open=round(bar.open, 2),
                high=round(bar.high, 2),
                low=round(bar.low, 2),
                close=round(bar.close, 2),
            )
            for bar in sampled_bars
        ]
        open_price = round(sampled_bars[0].open, 2)
        current_price = round(sampled_bars[-1].close, 2)
        high_price = round(max(bar.high for bar in sampled_bars), 2)
        low_price = round(min(bar.low for bar in sampled_bars), 2)
        change_abs = round(current_price - open_price, 2)
        change_pct = round(change_abs / open_price, 4) if open_price else 0.0
        return InstrumentChartSeries(
            label=label,
            points=points,
            open_price=open_price,
            current_price=current_price,
            high_price=high_price,
            low_price=low_price,
            change_abs=change_abs,
            change_pct=change_pct,
        )

    def _with_chart_overlays(
        self,
        series: InstrumentChartSeries,
        *,
        overlays: list[InstrumentChartOverlay],
    ) -> InstrumentChartSeries:
        if not overlays:
            return series
        return series.model_copy(update={"overlays": overlays})

    def _with_timeframe_market_overlays(
        self,
        series: InstrumentChartSeries,
        *,
        signal: FinalSignalCard | FinalSignalDetail | None,
    ) -> InstrumentChartSeries:
        overlays = self._build_market_overlays(
            signal=signal,
            current_price=series.current_price,
            reference_series=series,
        )
        return series.model_copy(
            update={
                "overlays": overlays,
                "signal_id": signal.signal_id if signal is not None and overlays else None,
                "signal_horizon": signal.horizon.value if signal is not None and overlays else None,
                "signal_summary": signal.summary if signal is not None and overlays else None,
            }
        )

    def _market_signals_by_horizon(
        self,
        *,
        root_details,
        preferred: FinalSignalCard | FinalSignalDetail | None,
    ) -> dict[str, FinalSignalCard | FinalSignalDetail]:
        candidates: list[FinalSignalCard | FinalSignalDetail] = []
        if preferred is not None:
            candidates.append(preferred)
        candidates.extend(root_details.active_signals)
        candidates.extend(
            self._list_signals(
                root=root_details.root.root_code,
                status=SignalStatus.ACTIVE,
                limit=20,
                seed_root_details=root_details,
            )
        )

        unique: dict[str, FinalSignalCard | FinalSignalDetail] = {}
        for candidate in candidates:
            if candidate.signal_id in unique:
                continue
            detailed = self.signal_service.get_signal(candidate.signal_id)
            unique[candidate.signal_id] = detailed or candidate

        directional = [
            item
            for item in unique.values()
            if item.status == SignalStatus.ACTIVE and item.direction_final.value != "no_edge"
        ]
        directional.sort(
            key=lambda item: (item.priority_score, item.confidence_final, item.generated_at),
            reverse=True,
        )

        by_horizon: dict[str, FinalSignalCard | FinalSignalDetail] = {}
        for candidate in directional:
            horizon = candidate.horizon.value
            if horizon not in by_horizon:
                by_horizon[horizon] = candidate
        return by_horizon

    def _select_timeframe_market_signal(
        self,
        *,
        label: str,
        signals_by_horizon: dict[str, FinalSignalCard | FinalSignalDetail],
    ) -> FinalSignalCard | FinalSignalDetail | None:
        for horizon in self.MARKET_TIMEFRAME_HORIZONS.get(label, ()):
            signal = signals_by_horizon.get(horizon)
            if signal is not None:
                return signal
        return None

    def _build_market_overlays(
        self,
        *,
        signal: FinalSignalCard | FinalSignalDetail | None,
        current_price: float,
        reference_series: InstrumentChartSeries,
    ) -> list[InstrumentChartOverlay]:
        if (
            signal is None
            or signal.direction_final.value == "no_edge"
            or current_price <= 0
        ):
            return []

        horizon = signal.horizon.value
        horizon_scale = self._market_horizon_level_scale(horizon)
        target_multiple = self._market_horizon_target_multiple(horizon)
        span = max(reference_series.high_price - reference_series.low_price, current_price * 0.006, 0.01)
        base_buffer = max(
            current_price * (0.004 + (1.0 - signal.confidence_final) * 0.012),
            span * 0.22,
        ) * horizon_scale
        parsed_invalidation = None
        if isinstance(signal, FinalSignalDetail):
            parsed_invalidation = self._extract_price_level_from_texts(
                texts=signal.invalidation_conditions,
                anchor=current_price,
            )

        if signal.direction_final.value == "bullish":
            invalidation_value = parsed_invalidation if parsed_invalidation is not None else current_price - base_buffer
            risk_distance = max(abs(current_price - invalidation_value), base_buffer)
            target_value = current_price + max(risk_distance * target_multiple, span * 0.33 * horizon_scale)
        else:
            invalidation_value = parsed_invalidation if parsed_invalidation is not None else current_price + base_buffer
            risk_distance = max(abs(current_price - invalidation_value), base_buffer)
            target_value = current_price - max(risk_distance * target_multiple, span * 0.33 * horizon_scale)

        overlays = [
            InstrumentChartOverlay(key="entry", value=round(current_price, 2), tone="entry"),
            InstrumentChartOverlay(key="invalidation", value=round(max(0.01, invalidation_value), 2), tone="risk"),
            InstrumentChartOverlay(key="target", value=round(max(0.01, target_value), 2), tone="target"),
        ]
        return overlays

    def _market_horizon_level_scale(self, horizon: str) -> float:
        return {
            "H1S": 0.82,
            "H3S": 1.0,
            "H2W": 1.35,
            "H4W": 1.85,
        }.get(horizon, 1.0)

    def _market_horizon_target_multiple(self, horizon: str) -> float:
        return {
            "H1S": 1.45,
            "H3S": 1.7,
            "H2W": 2.05,
            "H4W": 2.45,
        }.get(horizon, 1.8)

    def _extract_price_level_from_texts(self, *, texts: list[str], anchor: float) -> float | None:
        if anchor <= 0:
            return None

        pattern = re.compile(r"\d+(?:[ \u00A0]\d{3})*(?:[.,]\d+)?")
        for text in texts:
            for match in pattern.finditer(text):
                raw = match.group(0).replace(" ", "").replace("\u00A0", "").replace(",", ".")
                try:
                    candidate = float(raw)
                except ValueError:
                    continue
                relative_diff = abs(candidate - anchor) / max(anchor, 1.0)
                if 0.0 < candidate and relative_diff <= 0.35:
                    return round(candidate, 2)
        return None

    def _live_quote_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        primary_provider: str | None,
        secondary_provider: str | None,
        unit_hint: str | None,
        generated_at: datetime,
    ):
        return self.market_data_service.get_quote_snapshot(
            root_code=root_code,
            contract=contract,
            providers=self._market_data_providers(
                primary_provider=primary_provider,
                secondary_provider=secondary_provider,
            ),
            unit_hint=unit_hint,
            now=generated_at,
        )

    def _market_data_providers(
        self,
        *,
        primary_provider: str | None,
        secondary_provider: str | None,
    ) -> list[str]:
        providers: list[str] = []
        for provider in (primary_provider, secondary_provider):
            if provider is None:
                continue
            normalized = provider.strip().lower()
            if normalized and normalized not in providers:
                providers.append(normalized)
        if "moex" not in providers:
            providers.append("moex")
        return providers

    def _sample_bars(self, bars: list[Bar], *, max_points: int) -> list[Bar]:
        ordered = sorted(bars, key=lambda item: item.start_at)
        if len(ordered) <= max_points:
            return ordered

        last_index = len(ordered) - 1
        sampled_indices = {
            round(step * last_index / float(max_points - 1))
            for step in range(max_points)
        }
        return [ordered[index] for index in sorted(sampled_indices)]

    def _build_instrument_chart_series(
        self,
        *,
        label: str,
        points_count: int,
        current_price: float,
        trend_bias: float,
        volatility: float,
        conviction: float,
        generated_at: datetime,
        label_kind: str,
        lookback_step: timedelta,
        amplitude_scale: float,
    ) -> InstrumentChartSeries:
        seed = 0.17 + (points_count * 0.11)
        amplitude = max(0.0035, min(0.065, 0.006 + volatility * 0.02)) * amplitude_scale
        drift = conviction * 0.018 * amplitude_scale + trend_bias * 0.034 * amplitude_scale
        offsets: list[float] = []
        for index in range(points_count):
            progress = 0.0 if points_count == 1 else index / float(points_count - 1)
            wave = math.sin(progress * math.pi * 1.55 + seed) * amplitude
            echo = math.cos(progress * math.pi * 0.82 + seed / 2) * amplitude * 0.42
            offsets.append(((progress - 1.0) * drift) + wave + echo)

        last_offset = offsets[-1] if offsets else 0.0
        values = [
            round(max(current_price * 0.3, current_price * (1 + (offset - last_offset))), 2)
            for offset in offsets
        ]
        times = [
            generated_at - (lookback_step * (points_count - index - 1))
            for index in range(points_count)
        ]
        points: list[InstrumentChartPoint] = []
        previous_close = values[0] if values else current_price
        wick_scale = max(0.0015, min(0.0125, 0.002 + (volatility * 0.015)))
        for moment, value in zip(times, values, strict=False):
            open_value = previous_close
            close_value = value
            high_value = max(open_value, close_value) * (1 + wick_scale)
            low_value = min(open_value, close_value) * (1 - wick_scale)
            points.append(
                InstrumentChartPoint(
                    label=self._instrument_chart_label(moment, kind=label_kind),
                    value=close_value,
                    open=round(open_value, 2),
                    high=round(high_value, 2),
                    low=round(low_value, 2),
                    close=round(close_value, 2),
                )
            )
            previous_close = close_value
        open_price = values[0] if values else current_price
        high_price = max(values) if values else current_price
        low_price = min(values) if values else current_price
        change_abs = round((values[-1] if values else current_price) - open_price, 2)
        change_pct = round(change_abs / open_price, 4) if open_price else 0.0
        return InstrumentChartSeries(
            label=label,
            points=points,
            open_price=open_price,
            current_price=values[-1] if values else current_price,
            high_price=high_price,
            low_price=low_price,
            change_abs=change_abs,
            change_pct=change_pct,
        )

    def _instrument_chart_label(self, moment: datetime, *, kind: str) -> str:
        if kind == "hour":
            return moment.strftime("%H:%M")
        if kind == "weekday":
            return moment.strftime("%d.%m")
        return moment.strftime("%d.%m")

    def _instrument_price_baseline(self, root_code: str) -> float:
        baselines = {
            "SI": 94850.0,
            "BR": 68.4,
            "MXI": 342800.0,
        }
        return baselines.get(root_code.upper(), 1000.0 + float(len(root_code) * 125))

    def _instrument_price_unit(self, root_code: str) -> str:
        units = {
            "SI": "RUB",
            "BR": "USD",
            "MXI": "pts",
        }
        return units.get(root_code.upper(), "pts")

    def _safe_average(self, values) -> float:
        materialized = [float(value) for value in values]
        if not materialized:
            return 0.0
        return sum(materialized) / len(materialized)

    def _build_workspace_actions(
        self,
        *,
        focus_signal: FinalSignalDetail | None,
        root_details,
        evaluation: EvaluationSummary,
        admin_health,
    ) -> list[WorkspaceActionItem]:
        if focus_signal is None:
            return [
                WorkspaceActionItem(
                    title="Wait for a clean setup",
                    detail="No focus signal is active right now. Use the root lane to inspect other contracts or wait for the next recalculation cycle.",
                    tone="warning",
                ),
                WorkspaceActionItem(
                    title="Monitor platform health",
                    detail=f"Current platform status is {admin_health.status}; keep an eye on data freshness before acting on new signals.",
                    tone="neutral",
                ),
            ]

        roll_share = root_details.continuous_series.next_contract_share if root_details is not None else 0.0
        session_name = root_details.session.session_type.value if root_details is not None else "unknown"
        actions = [
            WorkspaceActionItem(
                title=f"Primary read: {focus_signal.direction_final.value} on {focus_signal.horizon.value}",
                detail=focus_signal.summary,
                tone="positive" if focus_signal.direction_final.value != "no_edge" else "neutral",
            ),
            WorkspaceActionItem(
                title="Execution context",
                detail=(
                    f"Session is {session_name}, skeptic verdict is {focus_signal.skeptic_verdict.value}, "
                    f"roll share is {roll_share:.0%}."
                ),
                tone="warning" if roll_share >= 0.35 else "neutral",
            ),
            WorkspaceActionItem(
                title="What breaks the thesis",
                detail="; ".join(focus_signal.invalidation_conditions[:3]) or "No explicit invalidation conditions were recorded for this signal yet.",
                tone="negative" if focus_signal.invalidation_conditions else "neutral",
            ),
            WorkspaceActionItem(
                title="What to journal next",
                detail=(
                    "Capture the reason for acting, the main risk, and whether market structure still matches the analyst drivers."
                    if not focus_signal.journal_entries
                    else "Update the journal with any change in thesis quality, execution timing, or post-mortem observations."
                ),
                tone="neutral",
            ),
        ]
        if evaluation.resolved_signals > 0:
            actions.append(
                WorkspaceActionItem(
                    title="Calibration anchor",
                    detail=(
                        f"There are {evaluation.resolved_signals} resolved signals available. "
                        f"Use them as a reference when judging whether confidence {focus_signal.confidence_final:.2f} is rich or average."
                    ),
                    tone="positive",
                )
            )
        return actions

    def _build_signal_visual(self, *, signal: FinalSignalDetail, root_details) -> SignalVisualSnapshot:
        metric_bars = [
            SignalMetricBar(
                label="Prob up",
                value=signal.probability_up,
                tone="positive" if signal.direction_final.value == "bullish" else "neutral",
                detail="Probability of upward continuation.",
            ),
            SignalMetricBar(
                label="Prob down",
                value=signal.probability_down,
                tone="negative" if signal.direction_final.value == "bearish" else "neutral",
                detail="Probability of downward continuation.",
            ),
            SignalMetricBar(
                label="Confidence",
                value=signal.confidence_final,
                tone="positive" if signal.confidence_final >= 0.6 else "warning",
                detail="Final calibrated confidence.",
            ),
            SignalMetricBar(
                label="Skeptic",
                value=signal.skeptic_score,
                tone="warning" if signal.skeptic_score < 0.55 else "positive",
                detail="Skeptic approval score.",
            ),
            SignalMetricBar(
                label="Roll risk",
                value=signal.roll_risk,
                tone="negative" if signal.roll_risk >= 0.5 else "warning",
                detail="Higher means contract transition risk is more relevant.",
            ),
            SignalMetricBar(
                label="Expiry risk",
                value=signal.expiry_risk,
                tone="negative" if signal.expiry_risk >= 0.5 else "warning",
                detail="Higher means expiry proximity matters more.",
            ),
        ]

        timeline = [
            SignalTimelineEvent(
                at=signal.generated_at,
                title="Signal issued",
                kind="signal",
                detail=f"{signal.direction_final.value} setup published for {signal.horizon.value}.",
                tone="positive" if signal.direction_final.value != "no_edge" else "neutral",
            )
        ]
        if root_details is not None:
            timeline.append(
                SignalTimelineEvent(
                    at=root_details.session.session_start_at,
                    title="Session context",
                    kind="session",
                    detail=(
                        f"{root_details.session.session_type.value} session, "
                        f"rule set {root_details.session.effective_rule_set}, "
                        f"roll share {root_details.continuous_series.next_contract_share:.0%}."
                    ),
                    tone="neutral",
                )
            )
        for entry in signal.journal_entries:
            timeline.append(
                SignalTimelineEvent(
                    at=entry.created_at,
                    title=entry.title,
                    kind=entry.kind.value,
                    detail=entry.note,
                    tone=(
                        "warning" if entry.kind == JournalEntryKind.RISK_NOTE
                        else "negative" if entry.kind == JournalEntryKind.POST_MORTEM
                        else "neutral"
                    ),
                )
            )
        if signal.resolution is not None:
            timeline.append(
                SignalTimelineEvent(
                    at=signal.resolution.resolved_at,
                    title="Resolution",
                    kind="resolution",
                    detail=(
                        f"{signal.resolution.outcome.value} with {signal.resolution.realized_return_bps:.1f} bps. "
                        f"{signal.resolution.resolution_note}"
                    ),
                    tone=(
                        "positive" if signal.resolution.outcome.value == "win"
                        else "negative" if signal.resolution.outcome.value == "loss"
                        else "warning"
                    ),
                )
            )
        timeline.sort(key=lambda item: self._coerce_utc(item.at))

        horizon_pulse: list[HorizonPulsePoint] = []
        if root_details is not None:
            related_signals = {item.horizon: item for item in root_details.active_signals}
            horizon_order = ["H1S", "H3S", "H2W", "H4W"]
            for horizon_code in horizon_order:
                feature = next((item for item in root_details.feature_snapshots if item.horizon.value == horizon_code), None)
                if feature is None:
                    continue
                related_signal = related_signals.get(feature.horizon)
                probability = related_signal.probability_up if related_signal is not None else 0.5
                tone = "positive" if probability >= 0.55 else "negative" if probability <= 0.45 else "neutral"
                horizon_pulse.append(
                    HorizonPulsePoint(
                        horizon=horizon_code,
                        signal_probability=probability,
                        return_score=feature.return_score,
                        realized_volatility=feature.realized_volatility,
                        trend_slope=feature.trend_slope,
                        tone=tone,
                    )
                )

        return SignalVisualSnapshot(
            metric_bars=metric_bars,
            timeline=timeline,
            horizon_pulse=horizon_pulse,
        )

    def _coerce_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _build_kpis(
        self,
        *,
        spotlight_signals: list[FinalSignalCard],
        evaluation: EvaluationSummary,
        admin_health,
        root_details,
    ) -> list[DashboardKpi]:
        active_session = root_details.session.session_type.value if root_details is not None else "unknown"
        next_share = root_details.continuous_series.next_contract_share if root_details is not None else 0.0
        status_tone = "positive" if admin_health.status == "ok" else "warning" if admin_health.status == "degraded" else "negative"
        evaluation_tone = "positive" if evaluation.resolved_signals > 0 else "warning"

        return [
            DashboardKpi(
                label="Live Root",
                value=root_details.root.root_code if root_details is not None else "n/a",
                tone="positive" if root_details is not None else "warning",
                detail="Current dashboard focus root.",
            ),
            DashboardKpi(
                label="Active Signals",
                value=str(len(spotlight_signals)),
                tone="positive" if spotlight_signals else "warning",
                detail="Visible active signals for the selected root.",
            ),
            DashboardKpi(
                label="Session",
                value=active_session,
                tone="neutral",
                detail="Current MOEX session classification.",
            ),
            DashboardKpi(
                label="Roll Share",
                value=f"{next_share:.0%}",
                tone="warning" if next_share >= 0.35 else "neutral",
                detail="Share migrating into the next contract.",
            ),
            DashboardKpi(
                label="Resolved",
                value=str(evaluation.resolved_signals),
                tone=evaluation_tone,
                detail="Signals available for calibration and quality checks.",
            ),
            DashboardKpi(
                label="Platform",
                value=admin_health.status,
                tone=status_tone,
                detail="Operational health snapshot across DB, sources and backups.",
            ),
        ]


def get_dashboard_service() -> DashboardService:
    session_factory = get_session_factory()
    repository = SqlAlchemyContractMasterRepository(session_factory)
    return DashboardService(
        repository,
        SqlAlchemySourceQualityRepository(session_factory),
        signal_service=SignalService(repository),
        evaluation_service=EvaluationService(repository),
        observability_service=ObservabilityService(repository),
        runtime_control_service=RuntimeControlService(repository),
        market_data_service=get_market_data_service(),
    )
