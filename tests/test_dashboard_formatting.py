from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

import apps.api.routes.dashboard_gate as dashboard_gate
from apps.api.routes.dashboard_formatting import (
    format_calendar_date,
    format_expiry_countdown,
    format_optional,
    format_price_value,
    format_signed_pct,
    format_signed_value,
    format_timestamp,
)
from apps.api.routes.dashboard_cards import render_action_item, render_journal_entry, render_related_signal
from apps.api.routes.dashboard_comparison import render_horizon_comparison, render_signal_diff
from apps.api.routes.dashboard_council_data import (
    council_bullets,
    council_joined,
    council_packet,
    council_role_labels,
)
from apps.api.routes.dashboard_control import (
    control_panel_data_mode_label,
    control_panel_data_mode_tone,
    control_panel_reference_sync_label,
    control_panel_reference_sync_source,
    control_panel_reference_sync_tone,
    primary_market_feed,
    render_control_panel,
    render_market_data_context,
    render_runtime_prompt_history,
    render_runtime_prompt_history_entry,
    runtime_prompt_approval_state_label,
    runtime_prompt_default_version_id,
    runtime_prompt_effective_rendered_prompt,
    runtime_prompt_effective_template,
    runtime_prompt_working_rendered_prompt,
)
from apps.api.routes.dashboard_delivery import (
    delivery_activity_filter_href,
    render_delivery_activity,
    render_delivery_activity_controls,
    render_delivery_activity_footer,
    render_delivery_windows,
)
from apps.api.routes.dashboard_delivery_data import group_delivery_activity
from apps.api.routes.dashboard_decision import render_decision_timeline, render_review_bundle
from apps.api.routes.dashboard_export import render_delivery_activity_export
from apps.api.routes.dashboard_gate import (
    DASHBOARD_DISABLED_DETAIL,
    DASHBOARD_FEATURE_FLAG,
    ensure_dashboard_enabled,
)
from apps.api.routes.dashboard_insight import render_confidence_decomposition, render_similar_setups
from apps.api.routes.dashboard_journal import render_journal_decision_log_item, render_journal_workspace_entry
from apps.api.routes.dashboard_language import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES, resolve_language
from apps.api.routes.dashboard_market import (
    format_level_distance,
    market_level_record,
    market_overlay_style,
    market_status_tone,
    render_market_snapshot,
    render_market_unavailable_snapshot,
)
from apps.api.routes.dashboard_onboarding import render_operator_onboarding
from apps.api.routes.dashboard_page_hints import page_hint
import apps.api.routes.dashboard_page_shell as dashboard_page_shell
from apps.api.routes.dashboard_page_shell import apply_page_utility_shell, render_page_utility_markup
from apps.api.routes.dashboard_quality import journal_filter_href, render_quality_pair
from apps.api.routes.dashboard_sidebar import render_page_sidebar, render_page_sidebar_styles
from apps.api.routes.dashboard_signal_list import render_signal_card, render_signal_row
from apps.api.routes.dashboard_surface import render_surface_state_strip, surface_state_palette
from apps.api.routes.dashboard_tags import render_tag_chips, render_tag_picker
from apps.api.routes.dashboard_trust import render_trust_ribbon
from apps.api.routes.dashboard_visuals import render_horizon_pulse, render_metric_bars, render_timeline
from apps.api.routes.dashboard_watchlist import render_watchlist
from apps.api.routes.dashboard_workspace import (
    render_attention_inbox,
    render_morning_brief,
    render_root_pulse_card,
    render_workspace_signal_tile,
)
import apps.api.routes.dashboard_workspace_data as dashboard_workspace_data
from apps.api.routes.dashboard_workspace_data import build_morning_brief, build_signal_workspace_snapshot
from apps.api.routes.dashboard_workflow import (
    render_workflow_chip,
    render_workflow_panel,
    workflow_state_hint,
    workflow_state_label,
    workflow_state_tone,
)
from libs.domain.contracts import JournalEntryKind, SignalStatus, SignalWorkflowState
from libs.preferences.contracts import (
    NotificationDeliveryActivityAction,
    NotificationDeliveryActivityExportFormat,
    NotificationDeliveryActivityFilters,
    NotificationDeliveryActivityGroup,
    NotificationDeliveryActivityItem,
    NotificationDeliveryActivityPagination,
    NotificationDeliveryWindow,
    NotificationEventKind,
)


def test_dashboard_formatting_helpers_match_operator_display_contract() -> None:
    assert format_price_value(96325) == "96 325.00"
    assert format_price_value(99.2) == "99.20"
    assert format_price_value(None) == "n/a"
    assert format_signed_value(12.5) == "+12.50"
    assert format_signed_pct(-0.0123) == "-1.23%"
    assert format_optional(0.81234) == "0.8123"
    assert format_timestamp(datetime(2026, 4, 24, 7, 30, tzinfo=UTC)) == "2026-04-24 10:30:00 MSK"
    assert format_calendar_date(date(2026, 6, 18), language="ru") == "18.06.2026"
    assert format_expiry_countdown(55, date(2026, 6, 18), language="en") == "55 \u00b7 until 2026-06-18"


def test_dashboard_sidebar_helpers_render_navigation_and_root_switch() -> None:
    roots = [
        SimpleNamespace(root_code="Si", active_contract="SiM6", base_asset="USD/RUB"),
        SimpleNamespace(root_code="BR", active_contract="BRK6", base_asset="Brent Crude"),
    ]

    html = render_page_sidebar("signal", root="BR", roots=roots, signal_id="SIG<demo>")
    styles = render_page_sidebar_styles("1320px")

    assert 'class="sidebar-link is-active"' in html
    assert 'href="/workspace/signals/SIG&lt;demo&gt;"' in html
    assert 'data-root-switch data-page-key="signal" data-fallback-path="/workspace"' in html
    assert 'value="BR" selected' in html
    assert "BR &middot; BRK6 &middot; Brent Crude" in html
    assert "grid-template-columns: 248px minmax(0, 1fr)" in styles
    assert "@media (max-width: 1040px)" in styles


def test_dashboard_market_helpers_match_chart_contract() -> None:
    series = SimpleNamespace(
        overlays=[
            SimpleNamespace(key="entry", value=100.0),
            SimpleNamespace(key="target", value=112.0),
            SimpleNamespace(key="ignored", value=None),
        ]
    )

    assert market_overlay_style("entry") == ("#17364d", "4 3")
    assert market_overlay_style("unknown") == ("#5c6970", "4 3")
    assert format_level_distance(100.0, 112.0) == "12.00%"
    assert format_level_distance(None, 112.0) == "n/a"
    assert market_level_record(series) == {"entry": 100.0, "target": 112.0}
    assert market_status_tone("fresh") == "positive"
    assert market_status_tone("stale") == "warning"
    assert market_status_tone("degraded") == "negative"


def test_dashboard_market_renderer_keeps_price_and_chart_contract() -> None:
    points = [
        SimpleNamespace(label="09:00", open=100.0, high=105.0, low=99.0, close=104.0),
        SimpleNamespace(label="10:00", open=104.0, high=108.0, low=103.0, close=106.0),
    ]
    overlays = [
        SimpleNamespace(key="entry", value=101.0),
        SimpleNamespace(key="invalidation", value=97.0),
        SimpleNamespace(key="target", value=112.0),
    ]
    series = SimpleNamespace(
        label="1W",
        points=points,
        overlays=overlays,
        current_price=106.0,
        open_price=100.0,
        high_price=108.0,
        low_price=99.0,
        change_abs=6.0,
        change_pct=0.06,
    )
    snapshot = SimpleNamespace(
        unit="RUB",
        status="fresh",
        status_detail=None,
        daily=series,
        weekly=series,
        monthly=series,
        root_code="Si",
        current_price=106.0,
        contract="SiM6",
        price_change_abs=6.0,
        price_change_pct=0.06,
        as_of=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
        price_source="fixture",
        base_asset="USD/RUB",
    )

    html = render_market_snapshot(snapshot, language="ru", signal_id="SIG<market>")
    unavailable = render_market_unavailable_snapshot(language="ru", root_code="Si", signal_id="SIG<market>")

    assert 'data-market-panel data-market-root-code="Si" data-market-signal-id="SIG&lt;market&gt;"' in html
    assert 'data-market-current-price' in html
    assert 'data-market-chart-card data-market-timeframe="1W"' in html
    assert "\u041d\u0435\u0434\u0435\u043b\u044f \u00b7 1W" in html
    assert "106.00 RUB" in html
    assert 'data-market-distance-bar' in html
    assert "\u0413\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b" in unavailable


def test_dashboard_route_keeps_market_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_market_snapshot as _render_market_snapshot" in source
    assert "_legacy_render_market_snapshot" not in source
    assert "_legacy_render_market_chart_card" not in source
    assert "_legacy_market_overlay_copy" not in source


def test_dashboard_trust_ribbon_renderer_escapes_operator_content() -> None:
    ribbon = SimpleNamespace(
        headline="Trust <fresh>",
        items=[
            SimpleNamespace(tone="positive", label="Feed", value="Live", detail="MOEX <ok>"),
            SimpleNamespace(tone="warning", label="Runtime", value="Aging", detail=None),
        ],
    )

    html = render_trust_ribbon(ribbon)

    assert '<section class="panel">' in html
    assert "<h2>Trust ribbon</h2>" in html
    assert "Trust &lt;fresh&gt;" in html
    assert "tone-positive" in html
    assert "MOEX &lt;ok&gt;" in html
    assert "Aging | " in html


def test_dashboard_route_keeps_trust_ribbon_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_trust_ribbon as _render_trust_ribbon" in source
    assert "def _render_trust_ribbon" not in source


def test_dashboard_operator_onboarding_renderer_guides_first_run_flow() -> None:
    ru_html = render_operator_onboarding("ru")
    en_html = render_operator_onboarding("en")

    assert 'data-operator-onboarding' in ru_html
    assert 'data-operator-onboarding-collapse' in ru_html
    assert 'data-operator-onboarding-dismiss' in ru_html
    assert 'data-operator-onboarding-body' in ru_html
    assert 'data-operator-glossary' in ru_html
    assert "\u041a\u0430\u043a \u0447\u0438\u0442\u0430\u0442\u044c workspace" in ru_html
    assert "\u0413\u043b\u043e\u0441\u0441\u0430\u0440\u0438\u0439 \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0430" in ru_html
    assert "\u043d\u0435 \u0442\u043e\u0440\u0433\u043e\u0432\u044b\u0439 \u043f\u0440\u0438\u043a\u0430\u0437" in ru_html
    assert "/workspace/runtime" in ru_html
    assert "How to read the workspace" in en_html
    assert "Hide for this browser" in en_html
    assert 'data-expand-label="Expand"' in en_html
    assert "decision support, not an order" in en_html


def test_dashboard_tag_helpers_escape_picker_and_chips() -> None:
    picker_html = render_tag_picker(["data issue", "good <catch>"])
    disabled_html = render_tag_picker(["late"], disabled=True)
    chips_html = render_tag_chips(["false urgency", "late <entry>"])
    empty_html = render_tag_chips([], empty="none yet")

    assert 'data-journal-tag-picker' in picker_html
    assert 'name="tags" value="data issue"' in picker_html
    assert "good &lt;catch&gt;" in picker_html
    assert 'value="late" disabled' in disabled_html
    assert 'data-journal-tags' in chips_html
    assert "late &lt;entry&gt;" in chips_html
    assert "none yet" in empty_html


def test_dashboard_route_keeps_operator_onboarding_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_operator_onboarding as _render_operator_onboarding" in source
    assert "def _render_operator_onboarding" not in source
    assert '<section class="panel operator-onboarding"' not in source
    assert "render_tag_picker as _render_tag_picker" in source
    assert "def _render_tag_picker" not in source


def test_dashboard_watchlist_renderer_escapes_notes_and_uses_signal_fallback() -> None:
    items = [
        SimpleNamespace(
            watch_key="default:Si:root",
            root_code="Si",
            signal_id=None,
            note="Watch <opening>",
            priority_rank=1,
            focus_reason="Review <opening>",
            last_reviewed_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
            review_state="reviewed_today",
            signal=None,
        ),
        SimpleNamespace(
            watch_key="default:BR:SIG <id>",
            root_code="BR",
            signal_id="SIG <id>",
            note="",
            priority_rank=2,
            focus_reason=None,
            last_reviewed_at=None,
            updated_at=None,
            review_state="review_due",
            signal=SimpleNamespace(summary="Signal <fallback>"),
        ),
    ]

    html = render_watchlist(items)
    empty_html = render_watchlist([])

    assert "<h2>Daily Watchlist Queue</h2>" in html
    assert 'data-watchlist-filters' in html
    assert 'data-watchlist-filter-review' in html
    assert 'data-watchlist-bulk-actions' in html
    assert 'data-watchlist-bulk-review' in html
    assert 'data-watchlist-bulk-remove' in html
    assert '<option value="Si">Si</option>' in html
    assert '<option value="BR">BR</option>' in html
    assert "#1 · Si" in html
    assert "Review &lt;opening&gt;" in html
    assert "Reviewed today" in html
    assert "Last reviewed 2026-04-24 10:30:00 MSK" in html
    assert 'data-watchlist-item data-watchlist-review-state="reviewed_today" data-watchlist-root="Si" data-watchlist-linked="root"' in html
    assert 'data-watchlist-watch-key="default:Si:root"' in html
    assert 'data-watchlist-review-state="review_due" data-watchlist-root="BR" data-watchlist-linked="signal"' in html
    assert 'data-watchlist-review data-watch-key="default:Si:root"' in html
    assert "Mark reviewed" in html
    assert 'data-watchlist-remove data-watch-key="default:BR:SIG &lt;id&gt;"' in html
    assert "Remove visible from queue" in html
    assert 'id="watchlist-action-status"' in html
    assert "Signal SIG &lt;id&gt;" in html
    assert "Signal &lt;fallback&gt;" in html
    assert "Review due" in html
    assert "No watchlist entries yet." in empty_html


def test_dashboard_route_keeps_watchlist_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_watchlist as _render_watchlist" in source
    assert "def _render_watchlist" not in source


def test_dashboard_decision_renderers_escape_timeline_and_review_content() -> None:
    event = SimpleNamespace(
        tone="warning",
        title="Validated <risk>",
        detail="Driver changed <fast>",
        at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
    )
    bundle = SimpleNamespace(
        highlights=["Good skeptic <catch>"],
        watched_root_codes=["BR", "Si"],
        review_due_items=1,
        reviewed_today_items=2,
        outcome_summary=["Si H1: win <12.0 bps>"],
        tag_suggestions=["data issue", "good skeptic catch"],
        next_review_actions=["Review <queued> item"],
        watched_roots=2,
        decisions_logged=3,
        ignored_signals=1,
        resolved_signals=4,
    )

    timeline_html = render_decision_timeline([event], title="Decision <log>")
    empty_timeline_html = render_decision_timeline([], title="Decision log")
    review_html = render_review_bundle(bundle)
    empty_review_html = render_review_bundle(
        SimpleNamespace(highlights=[], watched_roots=0, decisions_logged=0, ignored_signals=0, resolved_signals=0)
    )

    assert "Decision &lt;log&gt;" in timeline_html
    assert "Validated &lt;risk&gt;" in timeline_html
    assert "Driver changed &lt;fast&gt;" in timeline_html
    assert "2026-04-24 10:30:00 MSK" in timeline_html
    assert "No decision events yet." in empty_timeline_html
    assert "Good skeptic &lt;catch&gt;" in review_html
    assert "BR, Si" in review_html
    assert "1 due / 2 done today" in review_html
    assert "Si H1: win &lt;12.0 bps&gt;" in review_html
    assert "data issue" in review_html
    assert "Review &lt;queued&gt; item" in review_html
    assert "Next review actions" in review_html
    assert "1 / 4" in review_html
    assert "No review highlights yet." in empty_review_html


def test_dashboard_route_keeps_decision_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_decision_timeline as _render_decision_timeline" in source
    assert "render_review_bundle as _render_review_bundle" in source
    assert "def _render_decision_timeline" not in source
    assert "def _render_review_bundle" not in source


def test_dashboard_insight_renderers_escape_confidence_and_precedent_content() -> None:
    decomposition = SimpleNamespace(
        headline="Conviction <balanced>",
        factors=[
            SimpleNamespace(label="Analyst <trend>", value=0.823, detail="Role detail <ok>"),
            SimpleNamespace(label="Skeptic", value=-0.125, detail=None),
        ],
    )
    setup = SimpleNamespace(
        outcome="Resolved <win>",
        resolved_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
        realized_return_bps=12.34,
        similarity_score=0.876,
        note="Failed once <late>",
    )

    confidence_html = render_confidence_decomposition(decomposition)
    empty_confidence_html = render_confidence_decomposition(None)
    setups_html = render_similar_setups([setup])
    empty_setups_html = render_similar_setups([])

    assert "Conviction &lt;balanced&gt;" in confidence_html
    assert "Analyst &lt;trend&gt;" in confidence_html
    assert "0.82 | Role detail &lt;ok&gt;" in confidence_html
    assert "-0.12 | " in confidence_html
    assert empty_confidence_html == ""
    assert "Resolved &lt;win&gt;" in setups_html
    assert "2026-04-24 10:30:00 MSK" in setups_html
    assert "12.3 bps | similarity 0.88" in setups_html
    assert "Failed once &lt;late&gt;" in setups_html
    assert "No similar historical setups are available yet." in empty_setups_html


def test_dashboard_route_keeps_insight_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_confidence_decomposition as _render_confidence_decomposition" in source
    assert "render_similar_setups as _render_similar_setups" in source
    assert "def _render_confidence_decomposition" not in source
    assert "def _render_similar_setups" not in source


def test_dashboard_comparison_renderers_escape_horizon_and_diff_content() -> None:
    comparison = SimpleNamespace(
        items=[
            SimpleNamespace(
                horizon="H1 <fast>",
                direction="bullish <bias>",
                confidence=0.8123,
                skeptic_score=0.4567,
                attention_score=0.9876,
                summary="Momentum <strong>",
            )
        ]
    )
    diff = SimpleNamespace(
        summary="Changed <now>",
        probability_up_delta=0.123,
        confidence_delta=-0.045,
        skeptic_delta=0.067,
        freshness_delta=-0.089,
        drivers_added=["flow <bid>"],
        drivers_removed=[],
        invalidations_added=[],
        invalidations_removed=["old <level>"],
    )

    comparison_html = render_horizon_comparison(comparison)
    empty_comparison_html = render_horizon_comparison(None)
    diff_html = render_signal_diff(diff)
    empty_diff_html = render_signal_diff(None)

    assert "H1 &lt;fast&gt; | bullish &lt;bias&gt;" in comparison_html
    assert "confidence 0.81 | skeptic 0.46 | attention 0.99" in comparison_html
    assert "Momentum &lt;strong&gt;" in comparison_html
    assert "No horizon comparison is available yet." in empty_comparison_html
    assert "Changed &lt;now&gt;" in diff_html
    assert "Prob up +0.12 | confidence -0.04 | skeptic +0.07 | freshness -0.09" in diff_html
    assert "Added: flow &lt;bid&gt; | Removed: none" in diff_html
    assert "Added: none | Removed: old &lt;level&gt;" in diff_html
    assert empty_diff_html == ""


def test_dashboard_route_keeps_comparison_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_horizon_comparison as _render_horizon_comparison" in source
    assert "render_signal_diff as _render_signal_diff" in source
    assert "def _render_horizon_comparison" not in source
    assert "def _render_signal_diff" not in source


def test_dashboard_council_role_labels_preserve_language_contract() -> None:
    ru_labels = council_role_labels("ru")
    en_labels = council_role_labels("en")
    fallback_labels = council_role_labels("de")

    assert ru_labels["trend_vol"] == "Аналитик тренда и волатильности"
    assert ru_labels["skeptic"] == "Скептик"
    assert en_labels["trend_vol"] == "Trend / volatility analyst"
    assert en_labels["arbiter"] == "Arbiter"
    assert fallback_labels == en_labels


def test_dashboard_council_context_helpers_format_lists_and_packets() -> None:
    assert council_bullets(["driver <one>", "", "driver two"], "none") == "- driver <one>\n- driver two"
    assert council_bullets([], "none") == "- none"
    assert council_joined(["one", "", "two"], "none") == "one; two"
    assert council_joined([], "none") == "none"
    assert council_packet([("A", "value"), ("B", ""), ("C", "next")], "none") == "- A: value\n- C: next"
    assert council_packet([], "none") == "- none"


def test_dashboard_route_keeps_council_role_labels_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "council_bullets as _council_bullets" in source
    assert "council_joined as _council_joined" in source
    assert "council_packet as _council_packet" in source
    assert "council_role_labels as _council_role_labels" in source
    assert "def _bullets" not in source
    assert "def _joined" not in source
    assert "def _packet" not in source
    assert "role_labels = {" not in source
    assert "role_labels = _council_role_labels(language)" in source


def test_dashboard_workspace_lane_renderers_preserve_preview_contracts() -> None:
    root = SimpleNamespace(
        root_code="Si",
        base_asset="USD/RUB <spot>",
        headline="Root <headline>",
        tone="positive",
        active_signals=3,
        next_contract_share=0.25,
        current_price=96325.5,
        price_unit="R<UB>",
        price_change_pct=0.0123,
    )
    signal = SimpleNamespace(
        signal_id="SIG<demo>",
        root="Si",
        contract="SiM6",
        summary="Signal <summary>",
        direction_final=SimpleNamespace(value="bullish"),
        horizon=SimpleNamespace(value="H1"),
        confidence_final=0.8123,
        skeptic_score=0.4567,
        priority_score=99,
        workflow_state=SimpleNamespace(value="escalate"),
        status=SimpleNamespace(value="active"),
    )
    attention = SimpleNamespace(
        item_key="signal:SIG<attention>",
        item_type="signal",
        root_code="Si",
        signal_id="SIG<attention>",
        title="Signal <attention>",
        reason="Promoted <reason>.",
        what_changed="Confidence <changed>.",
        next_step="Next <step>.",
        tone="warning",
        priority_score=98,
        attention_score=87.6,
        workflow_state=SimpleNamespace(value="ready"),
        current_price=96325.5,
        price_unit="R<UB>",
        market_status="fresh",
        market_status_detail="Provider <detail>.",
        href="/workspace?root=Si&signal_id=SIG<attention>",
    )

    root_html = render_root_pulse_card(root, selected_root="Si", language="en")
    signal_html = render_workspace_signal_tile(signal, selected_signal_id="SIG<demo>", language="en")
    attention_html = render_attention_inbox([attention], language="en")

    assert 'data-root-preview-card data-root-code="Si"' in root_html
    assert 'class="rail-card tone-positive is-active"' in root_html
    assert "USD/RUB &lt;spot&gt;" in root_html
    assert "Root &lt;headline&gt;" in root_html
    assert "96 325.50 R&lt;UB&gt;" in root_html
    assert 'data-pin-root-preview data-root-code="Si" data-compare-slot="a"' in root_html
    assert 'data-signal-preview-card data-signal-id="SIG&lt;demo&gt;"' in signal_html
    assert 'class="signal-tile is-focus"' in signal_html
    assert "Signal &lt;summary&gt;" in signal_html
    assert "confidence 0.81" in signal_html
    assert "workflow escalated" in signal_html
    assert 'data-pin-signal-preview data-signal-id="SIG&lt;demo&gt;" data-compare-slot="b"' in signal_html
    assert 'data-attention-inbox' in attention_html
    assert 'data-attention-card' in attention_html
    assert 'data-attention-signal-id="SIG&lt;attention&gt;"' in attention_html
    assert "Signal &lt;attention&gt;" in attention_html
    assert "96 325.50 R&lt;UB&gt;" in attention_html
    assert "Next &lt;step&gt;." in attention_html
    assert '/workspace?root=Si&amp;signal_id=SIG&lt;attention&gt;' in attention_html


def test_dashboard_morning_brief_renders_operator_ritual_without_execution_language() -> None:
    attention = SimpleNamespace(
        title="Signal <one>",
        reason="Confidence changed <fast>.",
        href="/workspace?root=Si&signal_id=SIG<one>",
        market_status="degraded",
        market_status_detail="Feed stale <detail>.",
    )
    snapshot = SimpleNamespace(
        market_snapshot=SimpleNamespace(
            status="fresh",
            status_detail="MOEX feed <traceable>.",
            current_price=96325.5,
            unit="R<UB>",
        ),
        attention_inbox=[attention],
        review_bundle=SimpleNamespace(
            highlights=["Reviewed <overnight> delta."],
            outcome_summary=[],
            review_due_items=2,
            watched_root_codes=["Si", "BR"],
        ),
        telegram_delivery_ready=False,
        control_panel=SimpleNamespace(data_mode="degraded"),
    )

    html = render_morning_brief(snapshot, language="en")

    assert 'data-morning-brief' in html
    assert 'data-morning-brief-market' in html
    assert 'data-morning-brief-attention' in html
    assert 'data-morning-brief-delta' in html
    assert 'data-morning-brief-dont-chase' in html
    assert "Morning Command Brief" in html
    assert "signals-only" in html
    assert "MOEX feed &lt;traceable&gt;." in html
    assert "96 325.50 R&lt;UB&gt;" in html
    assert "/workspace?root=Si&amp;signal_id=SIG&lt;one&gt;" in html
    assert "Signal &lt;one&gt;" in html
    assert "Feed stale &lt;detail&gt;." in html
    assert "Reviewed &lt;overnight&gt; delta." in html
    assert "preview" in html
    assert "order" not in html.lower()
    assert "trade now" not in html.lower()


def test_dashboard_morning_brief_builder_returns_api_contract() -> None:
    attention = SimpleNamespace(
        title="Signal one",
        reason="Priority changed.",
        href="/workspace?root=Si",
        tone="warning",
        market_status="degraded",
        market_status_detail="Feed stale.",
    )
    snapshot = SimpleNamespace(
        market_snapshot=SimpleNamespace(
            status="fresh",
            status_detail="Traceable live feed.",
            current_price=96325.5,
            unit="RUB",
        ),
        attention_inbox=[attention],
        review_bundle=SimpleNamespace(
            highlights=["Overnight confidence changed."],
            outcome_summary=[],
            review_due_items=1,
            watched_root_codes=["Si", "BR", "MXI", "GD", "CNY"],
        ),
        control_panel=SimpleNamespace(data_mode="live"),
    )

    brief = build_morning_brief(snapshot, telegram_delivery_ready=False)

    assert brief.signals_only is True
    assert brief.market_status == "fresh"
    assert brief.last_price == 96325.5
    assert brief.price_unit == "RUB"
    assert brief.top_attention[0].title == "Signal one"
    assert brief.dont_chase[0].detail == "degraded: Feed stale."
    assert brief.review_highlights == ["Overnight confidence changed."]
    assert brief.review_due_items == 1
    assert brief.watched_roots == ["Si", "BR", "MXI", "GD"]
    assert brief.telegram_status == "preview"
    assert brief.data_mode == "live"


def test_dashboard_route_keeps_workspace_lane_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_attention_inbox as _render_attention_inbox" in source
    assert "render_morning_brief as _render_morning_brief" in source
    assert "render_root_pulse_card as _render_root_pulse_card" in source
    assert "render_workspace_signal_tile as _render_workspace_signal_tile" in source
    assert "def _render_attention_inbox" not in source
    assert "def _render_morning_brief" not in source
    assert "def _render_root_pulse_card" not in source
    assert "def _render_workspace_signal_tile" not in source


def test_dashboard_workspace_data_returns_404_for_unknown_signal(monkeypatch) -> None:
    fake_dashboard_service = SimpleNamespace(build_signal_snapshot=lambda signal_id: None)
    fake_container = SimpleNamespace(dashboard_service=fake_dashboard_service)

    monkeypatch.setattr(dashboard_workspace_data, "get_app_container", lambda: fake_container)

    try:
        build_signal_workspace_snapshot("SIG-missing")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Unknown signal: SIG-missing"
    else:
        raise AssertionError("missing workspace signal snapshots should return 404")


def test_dashboard_route_keeps_workspace_data_builders_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "build_workspace_snapshot as _build_workspace_snapshot" in source
    assert "build_preference_workspace_snapshot as _build_preference_workspace_snapshot" in source
    assert "build_signal_workspace_snapshot as _build_signal_workspace_snapshot" in source
    assert "def _build_workspace_snapshot" not in source
    assert "def _build_preference_workspace_snapshot" not in source
    assert "def _build_signal_workspace_snapshot" not in source


def test_dashboard_card_renderers_escape_action_journal_and_related_content() -> None:
    action = SimpleNamespace(tone="warning", title="Act <now>", detail="Check <feed>")
    journal = SimpleNamespace(
        title="Thesis <update>",
        kind=SimpleNamespace(value="risk"),
        author="Operator <one>",
        created_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
        note="Watch invalidation <line>",
        tags=["data issue", "good <catch>"],
    )
    signal = SimpleNamespace(
        signal_id="SIG<related>",
        root="Si",
        contract="SiM6",
        horizon=SimpleNamespace(value="H4"),
        summary="Related <setup>",
        confidence_final=0.8123,
        skeptic_score=0.4567,
        direction_final=SimpleNamespace(value="bullish <bias>"),
        workflow_state=SimpleNamespace(value="escalate"),
    )

    action_html = render_action_item(action)
    journal_html = render_journal_entry(journal)
    related_html = render_related_signal(signal)

    assert 'class="action-card tone-warning"' in action_html
    assert "Act &lt;now&gt;" in action_html
    assert "Check &lt;feed&gt;" in action_html
    assert "Thesis &lt;update&gt;" in journal_html
    assert "risk | Operator &lt;one&gt; | 2026-04-24 10:30:00 MSK" in journal_html
    assert "Watch invalidation &lt;line&gt;" in journal_html
    assert "data issue" in journal_html
    assert "good &lt;catch&gt;" in journal_html
    assert 'href="/workspace/signals/SIG&lt;related&gt;"' in related_html
    assert "Related &lt;setup&gt;" in related_html
    assert "confidence 0.81 | skeptic 0.46 | bullish &lt;bias&gt; | workflow escalated" in related_html


def test_dashboard_route_keeps_card_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_action_item as _render_action_item" in source
    assert "render_journal_entry as _render_journal_entry" in source
    assert "render_related_signal as _render_related_signal" in source
    assert "def _render_action_item" not in source
    assert "def _render_journal_entry" not in source
    assert "def _render_related_signal" not in source


def test_dashboard_journal_renderers_escape_decision_and_entry_content() -> None:
    signal = SimpleNamespace(
        signal_id="SIG<journal>",
        root="Si",
        contract="SiM6",
        horizon=SimpleNamespace(value="H4"),
        summary="Journal <setup>",
        direction_final=SimpleNamespace(value="bullish <bias>"),
        status=SimpleNamespace(value="active <status>"),
        workflow_state=SimpleNamespace(value="escalate"),
    )
    latest_entry = SimpleNamespace(
        title="Latest <note>",
        author="Operator <one>",
        created_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
    )
    decision_item = SimpleNamespace(
        signal=signal,
        latest_entry=latest_entry,
        why_now=["Driver <fresh>"],
        next_watch=["Watch <level>"],
        decision_summary="Validate <breakout>",
        updated_at=datetime(2026, 4, 24, 7, 45, tzinfo=UTC),
    )
    entry_item = SimpleNamespace(
        signal=signal,
        entry=SimpleNamespace(
            title="Thesis <update>",
            kind=SimpleNamespace(value="thesis <kind>"),
            note="Context <note>",
            author="Analyst <one>",
            created_at=datetime(2026, 4, 24, 8, 0, tzinfo=UTC),
            tags=["false urgency", "late <tag>"],
        ),
    )

    decision_html = render_journal_decision_log_item(decision_item)
    entry_html = render_journal_workspace_entry(entry_item)

    assert "Journal &lt;setup&gt;" in decision_html
    assert "bullish &lt;bias&gt; | active &lt;status&gt;" in decision_html
    assert "tone-escalate" in decision_html
    assert "Driver &lt;fresh&gt;" in decision_html
    assert "Watch &lt;level&gt;" in decision_html
    assert "Latest note: Latest &lt;note&gt; | Operator &lt;one&gt; | 2026-04-24 10:30:00 MSK" in decision_html
    assert 'href="/workspace/signals/SIG&lt;journal&gt;"' in decision_html
    assert "Thesis &lt;update&gt;" in entry_html
    assert "thesis &lt;kind&gt; | active &lt;status&gt;" in entry_html
    assert "Context &lt;note&gt;" in entry_html
    assert "false urgency" in entry_html
    assert "late &lt;tag&gt;" in entry_html
    assert "author Analyst &lt;one&gt; | created 2026-04-24 11:00:00 MSK" in entry_html


def test_dashboard_route_keeps_journal_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_journal_decision_log_item as _render_journal_decision_log_item" in source
    assert "render_journal_workspace_entry as _render_journal_workspace_entry" in source
    assert "def _render_journal_decision_log_item" not in source
    assert "def _render_journal_workspace_entry" not in source


def test_dashboard_control_renderers_escape_runtime_and_feed_content() -> None:
    primary_feed = SimpleNamespace(
        provider="MOEX <ISS>",
        owner="Owner <feed>",
        role="primary <role>",
        status="fresh <status>",
        detail="Feed <detail>",
        last_update_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
        primary=True,
    )
    fallback_feed = SimpleNamespace(
        provider="Fallback",
        owner="Fallback owner",
        role="backup",
        status="standby",
        detail=None,
        last_update_at=None,
        primary=False,
    )
    panel = SimpleNamespace(
        llm_product="LLM <product>",
        llm_model="Model <id>",
        llm_owner="Owner <runtime>",
        data_mode="snapshot",
        data_mode_detail="Data <detail>",
        latest_market_data_at=datetime(2026, 4, 24, 7, 45, tzinfo=UTC),
        reference_sync=SimpleNamespace(
            status="fresh",
            source="moex_iss",
            owner="Sync <owner>",
            detail="Sync <detail>",
            last_sync_at=datetime(2026, 4, 24, 8, 0, tzinfo=UTC),
        ),
        model_roles=[
            SimpleNamespace(
                role_label="Role <label>",
                product="Product <name>",
                model="Model <role>",
                owner="Owner <role>",
                detail="Role <detail>",
                control_mode="managed",
            )
        ],
        market_data_feeds=[fallback_feed, primary_feed],
    )

    assert control_panel_data_mode_tone("live") == "tone-positive"
    assert control_panel_data_mode_tone("snapshot") == "tone-warning"
    assert control_panel_data_mode_label("degraded_feed") == "Degraded feed"
    assert control_panel_data_mode_label("offline_mode") == "Offline Mode"
    assert control_panel_reference_sync_tone("stale") == "tone-warning"
    assert control_panel_reference_sync_label("fallback") == "Fallback"
    assert control_panel_reference_sync_source("bundled_fallback") == "Bundled fallback"
    approval_copy = {
        "approval_state_live": "Live",
        "approval_state_approved": "Approved",
        "approval_state_pending": "Pending",
    }
    assert runtime_prompt_approval_state_label("live", approval_copy) == "Live"
    assert runtime_prompt_approval_state_label("approved", approval_copy) == "Approved"
    assert runtime_prompt_approval_state_label("pending_approval", approval_copy) == "Pending"
    assert runtime_prompt_approval_state_label("needs_review", approval_copy) == "Needs Review"
    prompt_item = SimpleNamespace(
        role_key="arbiter",
        prompt_template="Base <prompt>",
        effective_prompt_template=None,
        effective_rendered_prompt=None,
        rendered_prompt=None,
    )
    override_prompt_item = SimpleNamespace(
        role_key="skeptic",
        prompt_template="Base <prompt>",
        effective_prompt_template="Effective <template>",
        effective_rendered_prompt="Effective <rendered>",
        rendered_prompt="Working <rendered>",
    )
    assert runtime_prompt_default_version_id(prompt_item) == "default:arbiter"
    assert runtime_prompt_effective_template(prompt_item) == "Base <prompt>"
    assert runtime_prompt_effective_rendered_prompt(prompt_item) == "Base <prompt>"
    assert runtime_prompt_working_rendered_prompt(prompt_item) == "Base <prompt>"
    assert runtime_prompt_effective_template(override_prompt_item) == "Effective <template>"
    assert runtime_prompt_effective_rendered_prompt(override_prompt_item) == "Effective <rendered>"
    assert runtime_prompt_working_rendered_prompt(override_prompt_item) == "Working <rendered>"
    history_copy = {
        **approval_copy,
        "approved_version": "Approved version",
        "pending_version": "Pending version",
        "current_version": "Current version",
        "restored_from": "Restored from",
        "version_state_pending_approval": "Pending approval",
        "release_note": "Release note",
        "restore": "Restore",
        "history": "History",
        "restore_default": "Restore default",
        "default_available": "Built-in default available.",
        "history_empty": "No history yet.",
    }
    history_version = SimpleNamespace(
        version_id="v2<script>",
        summary="Summary <x>",
        action="save <draft>",
        created_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
        restored_from_version_id="v1<old>",
        lifecycle_state="pending_approval",
        release_note="Changed <note>",
        restorable=True,
    )
    history_item = SimpleNamespace(
        role_key="arbiter<role>",
        current_version_id="v-current",
        approved_version_id="v-approved",
        pending_version_id="v2<script>",
        version_history=[history_version],
    )
    entry_html = render_runtime_prompt_history_entry(
        history_version,
        role_key=history_item.role_key,
        current_version_id=history_item.current_version_id,
        approved_version_id=history_item.approved_version_id,
        pending_version_id=history_item.pending_version_id,
        copy=history_copy,
    )
    history_html = render_runtime_prompt_history(history_item, copy=history_copy)
    empty_history_html = render_runtime_prompt_history(
        SimpleNamespace(role_key="skeptic", version_history=[]),
        copy=history_copy,
    )

    assert "Summary &lt;x&gt;" in entry_html
    assert "save &lt;draft&gt; · 2026-04-24 10:30:00 MSK" in entry_html
    assert "Pending version" in entry_html
    assert "Pending approval" in entry_html
    assert "Restored from v1&lt;old&gt;" in entry_html
    assert "Release note: Changed &lt;note&gt;" in entry_html
    assert 'data-role-key="arbiter&lt;role&gt;" data-version-id="v2&lt;script&gt;"' in entry_html
    assert 'data-version-id="default:arbiter&lt;role&gt;"' in history_html
    assert "Built-in default available." in history_html
    assert "No history yet." in empty_history_html
    assert primary_market_feed(panel) is primary_feed
    assert primary_market_feed(SimpleNamespace(market_data_feeds=[fallback_feed])) is fallback_feed

    context_html = render_market_data_context(panel)
    empty_context_html = render_market_data_context(SimpleNamespace(market_data_feeds=[], data_mode="live"))
    panel_html = render_control_panel(panel)

    assert "Owner &lt;feed&gt;" in context_html
    assert "Snapshot | Updated 2026-04-24 10:30:00 MSK" in context_html
    assert "No market-data feed is attached yet." in empty_context_html
    assert "LLM &lt;product&gt; &middot; Model &lt;id&gt;" in panel_html
    assert "Owner &lt;runtime&gt;" in panel_html
    assert "Data &lt;detail&gt;" in panel_html
    assert "Fresh &middot; MOEX ISS" in panel_html
    assert "Sync &lt;owner&gt; | Sync &lt;detail&gt;" in panel_html
    assert "Role &lt;label&gt;" in panel_html
    assert "Product &lt;name&gt; &middot; Model &lt;role&gt; &middot; Owner &lt;role&gt;" in panel_html
    assert "MOEX &lt;ISS&gt; &middot; Owner &lt;feed&gt;" in panel_html
    assert "primary &lt;role&gt; &middot; fresh &lt;status&gt; &middot; last 2026-04-24 10:30:00 MSK" in panel_html
    assert "Feed &lt;detail&gt;" in panel_html


def test_dashboard_route_keeps_control_panel_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_control_panel as _render_control_panel" in source
    assert "render_market_data_context as _render_market_data_context" in source
    assert "render_runtime_prompt_history as _render_runtime_prompt_history" in source
    assert "control_panel_data_mode_label as _control_panel_data_mode_label" in source
    assert "control_panel_reference_sync_label as _control_panel_reference_sync_label" in source
    assert "control_panel_reference_sync_source as _control_panel_reference_sync_source" in source
    assert "primary_market_feed as _primary_market_feed" in source
    assert "runtime_prompt_approval_state_label as _runtime_prompt_approval_state_label" in source
    assert "runtime_prompt_effective_rendered_prompt as _runtime_prompt_effective_rendered_prompt" in source
    assert "runtime_prompt_working_rendered_prompt as _runtime_prompt_working_rendered_prompt" in source
    assert "_runtime_prompt_effective_rendered_prompt(item)" in source
    assert "_runtime_prompt_working_rendered_prompt(item)" in source
    assert "_render_runtime_prompt_history(item, copy=copy)" in source
    assert "legacy_prompt_cards" not in source
    assert "def _render_control_panel" not in source
    assert "def _render_market_data_context" not in source
    assert "def _render_prompt_history_entry" not in source
    assert "def _render_prompt_history" not in source
    assert "def _control_panel_data_mode_label" not in source
    assert "def _control_panel_reference_sync_label" not in source
    assert "def _control_panel_reference_sync_source" not in source
    assert "def _primary_market_feed" not in source
    assert "def _approval_state_label" not in source
    assert 'default_version_id = f"default:{getattr(item, ' not in source
    assert 'effective_prompt_template = getattr(item, "effective_prompt_template"' not in source
    assert 'working_rendered_prompt = getattr(item, "rendered_prompt"' not in source


def test_dashboard_delivery_renderers_escape_windows_activity_and_filters() -> None:
    window = NotificationDeliveryWindow(
        job_id="job-1",
        label="Digest <window>",
        event_kind=NotificationEventKind.DIGEST,
        root_scope="Si <root>",
        next_run_at=datetime(2026, 4, 24, 7, 30, tzinfo=UTC),
        subscription_enabled=True,
        skip_next_pending=False,
        quiet_hours_policy="quiet <policy>",
        last_run_status="sent <status>",
        last_run_detail="detail <window>",
    )
    skipped_window = window.model_copy(
        update={
            "event_kind": NotificationEventKind.RESOLUTION,
            "subscription_enabled": False,
            "skip_next_pending": True,
        }
    )
    activity = NotificationDeliveryActivityItem(
        activity_id="activity-1",
        action=NotificationDeliveryActivityAction.SEND_NOW_FORCE,
        event_kind=NotificationEventKind.DIGEST,
        delivery_source="manual <source>",
        root_scope="Si <root>",
        status="sent",
        detail="Delivered <detail>",
        signal_ids=["SIG-1", "SIG-2"],
        provider_message_id="provider <id>",
        created_at=datetime(2026, 4, 24, 8, 0, tzinfo=UTC),
    )
    suppressed_activity = activity.model_copy(
        update={
            "activity_id": "activity-2",
            "status": "quiet_hours",
            "detail": "Telegram delivery suppressed because quiet hours are active.",
            "signal_ids": [],
            "provider_message_id": None,
        }
    )
    filters = NotificationDeliveryActivityFilters(
        root_scope="Si",
        event_kind=NotificationEventKind.DIGEST,
        status="sent",
    )
    groups = [
        NotificationDeliveryActivityGroup(value="digest", label="Digest <group>", count=2),
        NotificationDeliveryActivityGroup(value="resolution", label="Resolution", count=1),
    ]
    root_groups = [
        NotificationDeliveryActivityGroup(value="Si", label="Si <root>", count=2),
        NotificationDeliveryActivityGroup(value="BR", label="BR", count=1),
    ]
    status_groups = [NotificationDeliveryActivityGroup(value="sent", label="Sent <status>", count=2)]
    pagination = NotificationDeliveryActivityPagination(
        page=2,
        page_size=5,
        total_items=12,
        total_pages=3,
        has_previous=True,
        has_next=True,
    )

    windows_html = render_delivery_windows([window, skipped_window])
    activity_html = render_delivery_activity([activity, suppressed_activity])
    empty_windows_html = render_delivery_windows([])
    empty_activity_html = render_delivery_activity([])
    href = delivery_activity_filter_href(
        "/workspace/delivery-history",
        root="Si",
        signal_id="SIG<delivery>",
        activity_root_scope="Si",
        activity_event_kind=NotificationEventKind.DIGEST,
        activity_status="sent",
    )
    controls_html = render_delivery_activity_controls(
        base_path="/workspace/delivery-history",
        filters=filters,
        by_event_kind=groups,
        by_root_scope=root_groups,
        by_status=status_groups,
        root="Si",
        signal_id="SIG<delivery>",
    )
    footer_html = render_delivery_activity_footer(
        base_path="/workspace/delivery-history",
        export_path="/api/v1/workspace/delivery/activity/export",
        filters=filters,
        pagination=pagination,
        root="Si",
        signal_id="SIG<delivery>",
    )

    assert "Digest &lt;window&gt;" in windows_html
    assert "root Si &lt;root&gt; | next 2026-04-24 10:30:00 MSK" in windows_html
    assert "last run sent &lt;status&gt; | detail &lt;window&gt;" in windows_html
    assert 'data-event-kind="digest">Mute next digest</button>' in windows_html
    assert 'data-event-kind="resolution">Undo skip</button>' in windows_html
    assert "No delivery windows configured yet." in empty_windows_html
    assert "Manual send with quiet-hours override" in activity_html
    assert "digest | 2026-04-24 11:00:00 MSK" in activity_html
    assert "root Si &lt;root&gt; | source manual &lt;source&gt; | status sent" in activity_html
    assert "tone-positive" in activity_html
    assert "tone-warning" in activity_html
    assert 'data-delivery-reason' in activity_html
    assert "Reason trail:" in activity_html
    assert "Sent because delivery was allowed and Telegram accepted the message." in activity_html
    assert "Suppressed because quiet hours are active." in activity_html
    assert "Evidence:" in activity_html
    assert "Delivered &lt;detail&gt;" in activity_html
    assert "Telegram delivery suppressed because quiet hours are active." in activity_html
    assert "signals 2 | provider message provider &lt;id&gt;" in activity_html
    assert "no signal ids" in activity_html
    assert "No delivery actions recorded yet." in empty_activity_html
    assert href == (
        "/workspace/delivery-history?root=Si&signal_id=SIG%3Cdelivery%3E"
        "&activity_root_scope=Si&activity_event_kind=digest&activity_status=sent"
    )
    assert "Digest &lt;group&gt; (2)" in controls_html
    assert "Si &lt;root&gt; (2)" in controls_html
    assert "Sent &lt;status&gt; (2)" in controls_html
    assert "Digest &lt;group&gt; 2, Resolution 1" in controls_html
    assert "Page 2 of 3 | 12 total events | page size 5" in footer_html
    assert "activity_page=1&activity_page_size=5" in footer_html
    assert "activity_page=3&activity_page_size=5" in footer_html
    assert "export_format=csv" in footer_html
    assert "export_format=jsonl" in footer_html


def test_dashboard_route_keeps_delivery_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_delivery_windows as _render_delivery_windows" in source
    assert "render_delivery_activity as _render_delivery_activity" in source
    assert "delivery_activity_filter_href as _delivery_activity_filter_href" in source
    assert "render_delivery_activity_controls as _render_delivery_activity_controls" in source
    assert "render_delivery_activity_footer as _render_delivery_activity_footer" in source
    assert "def _render_delivery_windows" not in source
    assert "def _render_delivery_activity" not in source
    assert "def _delivery_activity_filter_href" not in source
    assert "def _render_delivery_activity_controls" not in source
    assert "def _render_delivery_activity_footer" not in source


def test_dashboard_delivery_data_groups_activity_by_count_and_label() -> None:
    items = [
        SimpleNamespace(status="sent", root_scope="Si"),
        SimpleNamespace(status="suppressed", root_scope="BR"),
        SimpleNamespace(status="sent", root_scope="BR"),
    ]

    grouped = group_delivery_activity(
        items,
        value_getter=lambda item: item.status,
        label_getter=lambda item: f"Status {item.status}",
    )

    assert [item.value for item in grouped] == ["sent", "suppressed"]
    assert [item.count for item in grouped] == [2, 1]
    assert grouped[0].label == "Status sent"


def test_dashboard_route_keeps_delivery_data_builders_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "build_delivery_activity_snapshot as _build_delivery_activity_snapshot" in source
    assert "build_delivery_history_snapshot as _build_delivery_history_snapshot" in source
    assert "def _build_delivery_activity_snapshot" not in source
    assert "def _build_delivery_history_snapshot" not in source
    assert "def _build_delivery_windows" not in source
    assert "def _group_delivery_activity" not in source


def test_dashboard_route_keeps_delivery_data_contracts_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "build_delivery_windows as _build_delivery_windows" not in source
    assert "NotificationDeliveryActivityAction" not in source
    assert "NotificationDeliveryActivityFilters" not in source
    assert "NotificationDeliveryActivityGroup" not in source
    assert "NotificationDeliveryActivityItem" not in source
    assert "NotificationDeliveryActivityPagination" not in source
    assert "NotificationDeliveryWindow" not in source
    assert "from datetime import UTC, datetime" in source


def test_dashboard_export_helpers_preserve_delivery_activity_csv_and_jsonl_contract() -> None:
    item = NotificationDeliveryActivityItem(
        activity_id="activity-1",
        action=NotificationDeliveryActivityAction.SEND_NOW,
        event_kind=NotificationEventKind.DIGEST,
        delivery_source="manual",
        root_scope="Si",
        status="sent",
        detail='Delivered "quoted" detail',
        signal_ids=["SIG-1", "SIG-2"],
        provider_message_id="provider-1",
        created_at=datetime(2026, 4, 24, 8, 0, tzinfo=UTC),
    )

    csv_body, csv_media_type = render_delivery_activity_export([item], NotificationDeliveryActivityExportFormat.CSV)
    jsonl_body, jsonl_media_type = render_delivery_activity_export(
        [item],
        NotificationDeliveryActivityExportFormat.JSONL,
    )

    assert csv_media_type == "text/csv"
    assert csv_body.splitlines()[0] == (
        "activity_id,action,event_kind,delivery_source,root_scope,status,detail,signal_count,provider_message_id,created_at,reason_label"
    )
    assert (
        '"activity-1","send_now","digest","manual","Si","sent","Delivered \'quoted\' detail",'
        '"2","provider-1","2026-04-24T08:00:00+00:00",'
        '"Sent because delivery was allowed and Telegram accepted the message."'
    ) in csv_body
    assert jsonl_media_type == "application/x-ndjson"
    assert '"activity_id": "activity-1"' in jsonl_body
    assert '"event_kind": "digest"' in jsonl_body
    assert '"signal_ids": ["SIG-1", "SIG-2"]' in jsonl_body
    assert '"reason_label": "Sent because delivery was allowed and Telegram accepted the message."' in jsonl_body


def test_dashboard_route_keeps_export_serialization_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_delivery_activity_export as _render_delivery_activity_export" in source
    assert "application/x-ndjson" not in source
    assert "activity_id,action,event_kind,delivery_source" not in source


def test_dashboard_gate_enforces_feature_flag_contract(monkeypatch) -> None:
    seen_flags: list[str] = []

    def fake_enabled(name: str) -> bool:
        seen_flags.append(name)
        return name != DASHBOARD_FEATURE_FLAG

    monkeypatch.setattr(dashboard_gate, "is_feature_enabled", fake_enabled)

    try:
        ensure_dashboard_enabled()
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == DASHBOARD_DISABLED_DETAIL
    else:
        raise AssertionError("dashboard gate should return a 404 when dashboard_ui is disabled")

    assert seen_flags == [DASHBOARD_FEATURE_FLAG]

    monkeypatch.setattr(dashboard_gate, "is_feature_enabled", lambda name: name == DASHBOARD_FEATURE_FLAG)
    ensure_dashboard_enabled()


def test_dashboard_route_keeps_feature_gate_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "ensure_dashboard_enabled as _ensure_dashboard_enabled" in source
    assert "from libs.runtime.feature_flags import is_feature_enabled" not in source
    assert "def _ensure_dashboard_enabled" not in source
    assert "Dashboard feature is disabled." not in source


def test_dashboard_language_resolver_prefers_query_then_cookie_then_default() -> None:
    assert LANGUAGE_COOKIE == "imoex_lang"
    assert SUPPORTED_LANGUAGES == {"ru", "en"}
    assert resolve_language(SimpleNamespace(query_params={"lang": "en"}, cookies={LANGUAGE_COOKIE: "ru"})) == "en"
    assert resolve_language(SimpleNamespace(query_params={}, cookies={LANGUAGE_COOKIE: "en"})) == "en"
    assert resolve_language(SimpleNamespace(query_params={"lang": "de"}, cookies={LANGUAGE_COOKIE: "en"})) == "ru"
    assert resolve_language(SimpleNamespace(query_params={"lang": " EN "}, cookies={})) == "en"
    assert resolve_language(SimpleNamespace(query_params={}, cookies={})) == "ru"


def test_dashboard_route_keeps_language_resolution_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "resolve_language as _resolve_language" in source
    assert "def _resolve_language" not in source
    assert "SUPPORTED_LANGUAGES =" not in source


def test_dashboard_page_hints_preserve_page_and_fallback_contract() -> None:
    assert page_hint("dashboard", "en").startswith("Read top to bottom")
    assert page_hint("workspace", "en") == (
        "Start with the focus signal and root lane, then review the decision pack, delivery calendar, and journal."
    )
    assert page_hint("runtime", "ru").startswith("Сначала проверьте маршрутизацию ролей")
    assert page_hint("unknown", "en") == page_hint("workspace", "en")
    assert page_hint("workspace", "de") == page_hint("workspace", "en")


def test_dashboard_route_keeps_page_hints_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "dashboard_page_hints" not in source
    assert "def _page_hint" not in source
    assert "Read top to bottom: start with the KPIs" not in source
    assert "Начните с сигнала в фокусе" not in source


def test_dashboard_page_shell_injects_utility_contract() -> None:
    html = apply_page_utility_shell(
        '<html lang="en"><head><title>Test</title></head><body><main>Body</main></body></html>',
        language="en",
        page_key="workspace",
    )

    assert '<div class="utility-shell">' in html
    assert 'id="ui-language-select" data-language-select' in html
    assert 'data-hint-box data-message="Start with the focus signal' in html
    assert 'document.cookie = "imoex_lang="' in html
    assert "window.__imoexMarketLiveRefreshStop" in html
    assert "<main>Body</main>" in html


def test_dashboard_page_shell_escapes_hint_copy(monkeypatch) -> None:
    monkeypatch.setattr(dashboard_page_shell, "page_hint", lambda page_key, language: "Look <here> & now")

    html = render_page_utility_markup(language="en", page_key="workspace")

    assert 'data-message="Look &lt;here&gt; &amp; now"' in html
    assert "Where to look?" in html


def test_dashboard_route_keeps_page_shell_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "apply_page_utility_shell as _apply_page_utility_shell" in source
    assert 'class="utility-shell"' not in source
    assert "document.cookie" not in source
    assert "LANGUAGE_COOKIE" not in source
    assert "data-language-select" not in source


def test_dashboard_signal_list_renderers_escape_compact_signal_content() -> None:
    signal = SimpleNamespace(
        root="Si <root>",
        contract="SiM6 <contract>",
        horizon=SimpleNamespace(value="H1 <horizon>"),
        direction_final=SimpleNamespace(value="bullish <bias>"),
        summary="Momentum <setup>",
        confidence_final=0.8123,
        skeptic_score=0.4567,
        priority_score=99,
        workflow_state=SimpleNamespace(value="escalate"),
    )

    card_html = render_signal_card(signal)
    row_html = render_signal_row(signal)

    assert '<article class="signal-card">' in card_html
    assert "Si &lt;root&gt; · SiM6 &lt;contract&gt;" in card_html
    assert "Momentum &lt;setup&gt;" in card_html
    assert "bullish &lt;bias&gt; · H1 &lt;horizon&gt;" in card_html
    assert "confidence 0.81" in card_html
    assert "skeptic 0.46" in card_html
    assert "priority 99" in card_html
    assert "workflow escalated" in card_html
    assert '<article class="signal-row">' in row_html
    assert "Si &lt;root&gt; · H1 &lt;horizon&gt; · bullish &lt;bias&gt;" in row_html
    assert "Momentum &lt;setup&gt; | workflow escalated" in row_html


def test_dashboard_route_keeps_signal_list_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_signal_card as _render_signal_card" in source
    assert "render_signal_row as _render_signal_row" in source
    assert "def _render_signal_card" not in source
    assert "def _render_signal_row" not in source


def test_dashboard_workflow_renderers_preserve_state_controls_contract() -> None:
    signal = SimpleNamespace(
        signal_id="SIG<workflow>",
        workflow_state=SignalWorkflowState.ESCALATE,
    )

    chip_html = render_workflow_chip(signal)
    panel_html = render_workflow_panel(signal, status_id="workflow<status>")
    empty_panel_html = render_workflow_panel(None, status_id="empty<status>")

    assert workflow_state_label(SignalWorkflowState.ESCALATE) == "escalated"
    assert workflow_state_tone(SignalWorkflowState.VALIDATING) == "review"
    assert workflow_state_hint(SignalWorkflowState.READY) == "The setup is actionable; manage it closely."
    assert 'class="workflow-chip tone-escalate"' in chip_html
    assert "escalated" in chip_html
    assert "<strong>escalated</strong>" in panel_html
    assert 'class="workflow-button tone-escalate is-active"' in panel_html
    assert 'data-workflow-state="escalate" data-signal-id="SIG&lt;workflow&gt;"' in panel_html
    assert "This signal needs a higher-attention review right now." in panel_html
    assert 'id="workflow&lt;status&gt;"' in panel_html
    assert "Pick a signal first" in empty_panel_html
    assert "Select a signal to set how you want to handle it." in empty_panel_html
    assert 'type="button" disabled' in empty_panel_html
    assert 'id="empty&lt;status&gt;"' in empty_panel_html


def test_dashboard_route_keeps_workflow_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_workflow_panel as _render_workflow_panel" in source
    assert "workflow_state_label as _workflow_state_label" in source
    assert "def _workflow_state_label" not in source
    assert "def _workflow_state_tone" not in source
    assert "def _workflow_state_hint" not in source
    assert "def _render_workflow_chip" not in source
    assert "def _render_workflow_panel" not in source


def test_dashboard_visual_renderers_escape_and_limit_operator_content() -> None:
    metrics = [
        SimpleNamespace(label="Pressure <buy>", value=5.0, max_value=10.0, detail="Driver <detail>", tone="positive"),
        SimpleNamespace(label="Overflow", value=15.0, max_value=10.0, detail=None, tone="warning"),
        SimpleNamespace(label="Zero max", value=5.0, max_value=0.0, detail="Zero <detail>", tone="negative"),
    ]
    timeline_items = [
        SimpleNamespace(
            tone="positive",
            title=f"Event <{index}>",
            at=datetime(2026, 4, 24, index, 0, tzinfo=UTC),
            kind=f"kind <{index}>",
            detail=f"Detail <{index}>",
        )
        for index in range(6)
    ]
    horizon_items = [
        SimpleNamespace(
            tone="warning",
            horizon="H1 <fast>",
            signal_probability=0.8123,
            return_score=0.4567,
            realized_volatility=0.1234,
            trend_slope=-0.2345,
        )
    ]

    full_metrics_html = render_metric_bars(metrics, compact=False)
    compact_metrics_html = render_metric_bars(metrics, compact=True)
    compact_timeline_html = render_timeline(timeline_items, compact=True)
    full_timeline_html = render_timeline(timeline_items[:1], compact=False)
    horizon_html = render_horizon_pulse(horizon_items)

    assert "Pressure &lt;buy&gt;" in full_metrics_html
    assert "Driver &lt;detail&gt;" in full_metrics_html
    assert 'style="width:50%"' in full_metrics_html
    assert 'style="width:100%"' in full_metrics_html
    assert 'style="width:0%"' in full_metrics_html
    assert "Driver &lt;detail&gt;" not in compact_metrics_html
    assert "No chart data available yet." in render_metric_bars([], compact=False)
    assert "Event &lt;0&gt;" not in compact_timeline_html
    assert "Event &lt;2&gt;" in compact_timeline_html
    assert "Event &lt;5&gt;" in compact_timeline_html
    assert "kind &lt;0&gt;" in full_timeline_html
    assert "Detail &lt;0&gt;" in full_timeline_html
    assert "No lifecycle events recorded yet." in render_timeline([], compact=True)
    assert "H1 &lt;fast&gt;" in horizon_html
    assert "signal probability 0.81" in horizon_html
    assert "return score 0.46" in horizon_html
    assert "volatility 0.12 | trend -0.23" in horizon_html
    assert "No horizon pulse data available yet." in render_horizon_pulse([])


def test_dashboard_route_keeps_visual_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_metric_bars as _render_metric_bars" in source
    assert "render_timeline as _render_timeline" in source
    assert "render_horizon_pulse as _render_horizon_pulse" in source
    assert "def _render_metric_bars" not in source
    assert "def _render_timeline" not in source
    assert "def _render_horizon_pulse" not in source


def test_dashboard_quality_helpers_escape_quality_and_build_journal_filters() -> None:
    pair = SimpleNamespace(
        provider_a="MOEX <ISS>",
        provider_b="Fallback <bundle>",
        contracts_count=12,
        latest_contract="SiM6 <contract>",
        mismatch_rate_overlap=0.12345,
    )

    html = render_quality_pair(pair)

    assert journal_filter_href() == "/workspace/journal"
    assert journal_filter_href(root="Si", status=SignalStatus.ACTIVE, kind=JournalEntryKind.THESIS) == (
        "/workspace/journal?root=Si&status=active&kind=thesis"
    )
    assert journal_filter_href(root="Si", tag="data issue") == "/workspace/journal?root=Si&tag=data+issue"
    assert "MOEX &lt;ISS&gt; vs Fallback &lt;bundle&gt;" in html
    assert "contracts 12 · latest SiM6 &lt;contract&gt; · mismatch 0.1235" in html
    assert "mismatch n/a" in render_quality_pair(pair.__class__(**{**pair.__dict__, "mismatch_rate_overlap": None}))
    assert "latest n/a" in render_quality_pair(pair.__class__(**{**pair.__dict__, "latest_contract": None}))


def test_dashboard_route_keeps_quality_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "journal_filter_href as _journal_filter_href" in source
    assert "render_quality_pair as _render_quality_pair" in source
    assert "def _journal_filter_href" not in source
    assert "def _render_quality_pair" not in source


def test_dashboard_surface_state_strip_escapes_state_cards_and_preserves_palette() -> None:
    items = [
        {
            "tone": "warning",
            "label": "Market <data>",
            "status": "aging <soon>",
            "detail": "Feed <detail>",
        },
        {
            "tone": "unknown",
            "label": "Runtime",
            "status": "ok",
            "detail": "No issues",
        },
    ]

    html = render_surface_state_strip(
        strip_key="workspace<state>",
        title="State <strip>",
        note="Trust <note>",
        items=items,
    )

    assert surface_state_palette("positive") == ("rgba(47, 126, 87, 0.14)", "rgba(47, 126, 87, 0.28)", "#2f7e57")
    assert surface_state_palette("negative") == ("rgba(180, 74, 61, 0.14)", "rgba(180, 74, 61, 0.28)", "#b44a3d")
    assert surface_state_palette("warning") == ("rgba(186, 112, 33, 0.14)", "rgba(186, 112, 33, 0.28)", "#ba7021")
    assert surface_state_palette("neutral") == ("rgba(23, 56, 79, 0.08)", "rgba(23, 56, 79, 0.12)", "#17384f")
    assert render_surface_state_strip(strip_key="empty", title="Empty", note="None", items=[]) == ""
    assert 'data-surface-state-strip="workspace&lt;state&gt;"' in html
    assert 'data-state-tone="warning"' in html
    assert "State &lt;strip&gt;" in html
    assert "Trust &lt;note&gt;" in html
    assert "Market &lt;data&gt;" in html
    assert "aging &lt;soon&gt;" in html
    assert "Feed &lt;detail&gt;" in html
    assert 'data-state-tone="unknown"' in html


def test_dashboard_route_keeps_surface_state_rendering_outside_route_module() -> None:
    source = Path("apps/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert "render_surface_state_strip as _render_surface_state_strip" in source
    assert "def _surface_state_palette" not in source
    assert "def _render_surface_state_strip" not in source
