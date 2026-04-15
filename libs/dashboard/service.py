from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.dashboard.contracts import (
    DashboardKpi,
    MarketDataFeedStatus,
    ModelRoleAssignment,
    DashboardQualityPair,
    DashboardSnapshot,
    HorizonPulsePoint,
    JournalWorkspaceEntry,
    JournalWorkspaceSnapshot,
    RuntimeControlPanel,
    SignalMetricBar,
    SignalTimelineEvent,
    SignalVisualSnapshot,
    WorkspaceActionItem,
    WorkspaceSignalSnapshot,
    WorkspaceRootPulse,
    WorkspaceSnapshot,
)
from libs.domain.contracts import EvaluationSummary, FinalSignalCard, FinalSignalDetail, JournalEntryKind, SignalStatus
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService, get_contract_master_service
from libs.evaluation.service import EvaluationService
from libs.observability.service import ObservabilityService
from libs.quality.repository import SqlAlchemySourceQualityRepository
from libs.signals.service import SignalService
from libs.utils.db import get_session_factory


class DashboardService:
    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        quality_repository: SqlAlchemySourceQualityRepository,
        *,
        contract_service: ContractMasterService | None = None,
        signal_service: SignalService | None = None,
        evaluation_service: EvaluationService | None = None,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self.repository = repository
        self.quality_repository = quality_repository
        self.contract_service = contract_service or get_contract_master_service()
        self.signal_service = signal_service or SignalService(repository)
        self.evaluation_service = evaluation_service or EvaluationService(repository)
        self.observability_service = observability_service or ObservabilityService(repository)

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

        return WorkspaceSnapshot(
            generated_at=generated_at,
            selected_root=selected_root,
            selected_signal_id=selected_signal_id,
            roots=roots,
            pulses=self._build_pulses(roots=roots, active_signals=all_active, selected_root=selected_root),
            signal_lane=signal_lane,
            focus_signal=focus_signal,
            root_details=root_details,
            evaluation=evaluation,
            admin_health=admin_health,
            quality_pairs=quality_pairs,
            control_panel=control_panel,
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
        )

    def build_signal_snapshot(self, *, signal_id: str) -> WorkspaceSignalSnapshot | None:
        signal = self._materialize_signal_detail(signal_id)
        if signal is None:
            return None

        root_details = self.contract_service.get_root_deep_dive(signal.root)
        related_signals = self._list_signals(
            root=signal.root,
            limit=6,
            seed_root_details=root_details,
        )
        related_signals = [item for item in related_signals if item.signal_id != signal.signal_id][:5]
        evaluation = self.evaluation_service.summarize(root=signal.root, top_k=3, limit=200)
        return WorkspaceSignalSnapshot(
            generated_at=datetime.now(UTC),
            signal=signal,
            root_details=root_details,
            related_signals=related_signals,
            evaluation=evaluation,
            visual=self._build_signal_visual(signal=signal, root_details=root_details),
        )

    def build_journal_snapshot(
        self,
        *,
        root: str | None = None,
        status: SignalStatus | None = None,
        kind: JournalEntryKind | None = None,
        signal_id: str | None = None,
        limit: int = 120,
    ) -> JournalWorkspaceSnapshot:
        roots = self.contract_service.list_roots()
        related_signals = self._list_signals(root=root, status=status, limit=max(20, min(limit, 120)))
        entries: list[JournalWorkspaceEntry] = []

        # Materialize journal across the current signal universe. This keeps the UX stable even on a fresh DB.
        for signal in related_signals:
            detail = self.signal_service.get_signal(signal.signal_id)
            if detail is None:
                detail = self._materialize_signal_detail(signal.signal_id)
            if detail is None:
                continue
            for entry in detail.journal_entries:
                if kind is not None and entry.kind != kind:
                    continue
                entries.append(JournalWorkspaceEntry(entry=entry, signal=signal))

        entries.sort(key=lambda item: item.entry.created_at, reverse=True)
        if signal_id is not None:
            entries = [item for item in entries if item.signal.signal_id == signal_id]

        selected_signal_id = signal_id
        if selected_signal_id is None and entries:
            selected_signal_id = entries[0].signal.signal_id

        return JournalWorkspaceSnapshot(
            generated_at=datetime.now(UTC),
            roots=roots,
            selected_root=root,
            selected_status=status,
            selected_kind=kind,
            selected_signal_id=selected_signal_id,
            entries=entries[:limit],
            related_signals=related_signals[:12],
            total_entries=len(entries),
            thesis_entries=sum(1 for item in entries if item.entry.kind == JournalEntryKind.THESIS),
            risk_entries=sum(1 for item in entries if item.entry.kind == JournalEntryKind.RISK_NOTE),
            post_mortems=sum(1 for item in entries if item.entry.kind == JournalEntryKind.POST_MORTEM),
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
        latest_market_data_at = max(
            (item.last_update_at for item in feeds if item.last_update_at is not None),
            default=None,
        )
        return RuntimeControlPanel(
            generated_at=generated_at,
            llm_owner="OpenAI",
            llm_product="ChatGPT",
            llm_model="gpt-5",
            model_roles=self._build_model_roles(),
            market_data_feeds=feeds,
            latest_market_data_at=latest_market_data_at,
        )

    def _build_model_roles(self) -> list[ModelRoleAssignment]:
        detail = "Temporary fixed mapping until configurable role routing is added."
        return [
            ModelRoleAssignment(
                role_key="trend_vol",
                role_label="Trend / volatility analyst",
                owner="OpenAI",
                product="ChatGPT",
                model="gpt-5",
                detail=detail,
            ),
            ModelRoleAssignment(
                role_key="flow_liquidity",
                role_label="Flow / liquidity analyst",
                owner="OpenAI",
                product="ChatGPT",
                model="gpt-5",
                detail=detail,
            ),
            ModelRoleAssignment(
                role_key="oi_roll",
                role_label="OI / roll analyst",
                owner="OpenAI",
                product="ChatGPT",
                model="gpt-5",
                detail=detail,
            ),
            ModelRoleAssignment(
                role_key="macro_event",
                role_label="Macro-event analyst",
                owner="OpenAI",
                product="ChatGPT",
                model="gpt-5",
                detail=detail,
            ),
            ModelRoleAssignment(
                role_key="skeptic",
                role_label="Skeptic",
                owner="OpenAI",
                product="ChatGPT",
                model="gpt-5",
                detail=detail,
            ),
            ModelRoleAssignment(
                role_key="arbiter",
                role_label="Arbiter",
                owner="OpenAI",
                product="ChatGPT",
                model="gpt-5",
                detail=detail,
            ),
        ]

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
    ) -> list[WorkspaceRootPulse]:
        pulses: list[WorkspaceRootPulse] = []
        for item in roots:
            deep_dive = self.contract_service.get_root_deep_dive(item.root_code)
            session_type = deep_dive.session.session_type if deep_dive is not None else None
            next_share = deep_dive.continuous_series.next_contract_share if deep_dive is not None else 0.0
            root_signals = [signal for signal in active_signals if signal.root == item.root_code]
            top_signal = root_signals[0] if root_signals else None
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
                    headline=headline,
                    tone=tone,
                )
            )
        return pulses

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
    )
