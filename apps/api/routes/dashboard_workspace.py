from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_price_value, format_signed_pct


def render_root_pulse_card(item, *, selected_root: str, language: str) -> str:
    price_line = f"{item.active_signals} active | roll {item.next_contract_share:.0%}"
    if item.current_price is not None:
        unit = f" {escape(item.price_unit)}" if item.price_unit else ""
        price_line = (
            f"L {format_price_value(item.current_price)}{unit} | "
            f"D {format_signed_pct(item.price_change_pct)} | "
            f"{item.active_signals} active | roll {item.next_contract_share:.0%}"
        )
    copy = _workspace_lane_copy(language, root_card=True)
    preview_buttons = "".join(
        (
            f'<button class="rail-preview-button{" is-active" if timeframe == "1D" else ""}" '
            f'type="button" data-root-preview-button data-root-code="{escape(item.root_code)}" '
            f'data-timeframe="{timeframe}">{timeframe}</button>'
        )
        for timeframe in ("1D", "1W", "1M")
    )
    return (
        f'<article class="rail-card tone-{escape(item.tone)}{" is-active" if item.root_code == selected_root else ""}" '
        f'data-root-preview-card data-root-code="{escape(item.root_code)}">'
        f'<a class="rail-card-link" href="/workspace?root={escape(item.root_code)}">'
        f"<strong>{escape(item.root_code)}</strong>"
        f"<span>{escape(item.base_asset)}</span>"
        f"<small>{escape(item.headline)}</small>"
        f'<em data-root-price-line data-active-signals="{item.active_signals}" data-roll-share="{item.next_contract_share:.0%}">{price_line}</em>'
        f'<div class="market-level-chip tone-neutral" data-root-level-chip><strong>{escape(copy["level_waiting"])}</strong><span>{escape(copy["level_waiting_note"])}</span></div>'
        "</a>"
        '<div class="rail-card-footer">'
        f'<div class="rail-card-tabs">{preview_buttons}</div>'
        f'<a class="rail-open-link" href="/workspace?root={escape(item.root_code)}">{escape(copy["open"])}</a>'
        "</div>"
        f'<div class="rail-preview-popover" hidden data-root-preview-popover data-root-code="{escape(item.root_code)}">'
        '<div class="rail-preview-head">'
        f'<strong>{escape(item.root_code)} \u00b7 <span data-root-preview-label>1D</span></strong>'
        f'<small data-root-preview-updated>{escape(copy["preview_ready"])}</small>'
        "</div>"
        f'<div class="rail-preview-chart" data-root-preview-chart><div class="empty">{escape(copy["preview_note"])}</div></div>'
        f'<div class="rail-preview-meta" data-root-preview-meta>{escape(price_line)}</div>'
        '<div class="signal-preview-actions">'
        f'<button class="preview-pin-button" type="button" data-pin-root-preview data-root-code="{escape(item.root_code)}" data-compare-slot="a" data-timeframe="1D">{escape(copy["pin_a"])}</button>'
        f'<button class="preview-pin-button" type="button" data-pin-root-preview data-root-code="{escape(item.root_code)}" data-compare-slot="b" data-timeframe="1D">{escape(copy["pin_b"])}</button>'
        f'<a class="rail-open-link" href="/workspace?root={escape(item.root_code)}">{escape(copy["open"])}</a>'
        "</div>"
        "</div>"
        "</article>"
    )


def render_workspace_signal_tile(signal, selected_signal_id: str | None, *, language: str) -> str:
    is_focus = signal.signal_id == selected_signal_id or (
        selected_signal_id is None and getattr(signal.status, "value", signal.status) == "active"
    )
    copy = _workspace_lane_copy(language, root_card=False)
    preview_buttons = "".join(
        (
            f'<button class="signal-preview-button{" is-active" if timeframe == "1D" else ""}" '
            f'type="button" data-signal-preview-button data-signal-id="{escape(signal.signal_id)}" '
            f'data-timeframe="{timeframe}">{timeframe}</button>'
        )
        for timeframe in ("1D", "1W", "1M")
    )
    return (
        f'<article class="signal-tile{" is-focus" if is_focus else ""}" '
        f'data-signal-preview-card data-signal-id="{escape(signal.signal_id)}">'
        f'<a class="signal-tile-link" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">'
        '<div class="signal-top">'
        f'<div><strong>{escape(signal.root)} | {escape(signal.contract)}</strong><p class="muted">{escape(signal.summary)}</p></div>'
        f'<span class="badge">{escape(signal.direction_final.value)} | {escape(signal.horizon.value)}</span>'
        "</div>"
        '<div class="metric-row">'
        f"<small>confidence {signal.confidence_final:.2f}</small>"
        f"<small>skeptic {signal.skeptic_score:.2f}</small>"
        f"<small>priority {signal.priority_score}</small>"
        f"<small>workflow {_workflow_state_label(signal.workflow_state)}</small>"
        "</div>"
        f'<div class="market-level-chip tone-neutral" data-signal-level-chip><strong>{escape(copy["level_waiting"])}</strong><span>{escape(copy["level_waiting_note"])}</span></div>'
        "</a>"
        '<div class="signal-tile-footer">'
        f'<div class="signal-preview-tabs">{preview_buttons}</div>'
        f'<a class="rail-open-link" href="/workspace/signals/{escape(signal.signal_id)}">{escape(copy["open"])}</a>'
        "</div>"
        f'<div class="signal-preview-popover" hidden data-signal-preview-popover data-signal-id="{escape(signal.signal_id)}">'
        '<div class="signal-preview-head">'
        f'<strong>{escape(signal.root)} | {escape(signal.horizon.value)} | <span data-signal-preview-label>1D</span></strong>'
        f'<small data-signal-preview-updated>{escape(copy["preview_ready"])}</small>'
        "</div>"
        f'<div class="signal-preview-chart" data-signal-preview-chart><div class="empty">{escape(copy["preview_note"])}</div></div>'
        '<div class="signal-preview-grid" data-signal-preview-grid></div>'
        f'<div class="signal-preview-summary" data-signal-preview-summary>{escape(signal.summary)}</div>'
        '<div class="signal-preview-actions">'
        f'<button class="preview-pin-button" type="button" data-pin-signal-preview data-signal-id="{escape(signal.signal_id)}" data-compare-slot="a" data-timeframe="1D">{escape(copy["pin_a"])}</button>'
        f'<button class="preview-pin-button" type="button" data-pin-signal-preview data-signal-id="{escape(signal.signal_id)}" data-compare-slot="b" data-timeframe="1D">{escape(copy["pin_b"])}</button>'
        f'<a class="rail-open-link" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">{escape(copy["focus"])}</a>'
        f'<a class="rail-open-link" href="/workspace/signals/{escape(signal.signal_id)}">{escape(copy["open"])}</a>'
        "</div>"
        "</div>"
        "</article>"
    )


def _workspace_lane_copy(language: str, *, root_card: bool) -> dict[str, str]:
    if root_card:
        return {
            "open": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c" if language == "ru" else "Open",
            "preview_ready": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0442\u0430\u0439\u043c\u0444\u0440\u0435\u0439\u043c" if language == "ru" else "Pick a timeframe",
            "preview_note": "\u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u0441\u0432\u0435\u0447\u0435\u0439 \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u0445\u043e\u0434\u0430" if language == "ru" else "Quick candle preview without navigation",
            "pin_a": "\u0421\u0435\u0440\u0438\u044f A" if language == "ru" else "Root A",
            "pin_b": "\u0421\u0435\u0440\u0438\u044f B" if language == "ru" else "Root B",
            "level_waiting": "\u0416\u0434\u0451\u043c \u0443\u0440\u043e\u0432\u043d\u0438" if language == "ru" else "Waiting for levels",
            "level_waiting_note": "\u041d\u0443\u0436\u043d\u044b \u0432\u0445\u043e\u0434, \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f \u0438 \u0446\u0435\u043b\u044c." if language == "ru" else "Need entry, invalidation, and target.",
        }
    return {
        "open": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c" if language == "ru" else "Open",
        "focus": "\u0412 \u0444\u043e\u043a\u0443\u0441" if language == "ru" else "Focus",
        "pin_a": "\u0421\u0438\u0433\u043d\u0430\u043b A" if language == "ru" else "Signal A",
        "pin_b": "\u0421\u0438\u0433\u043d\u0430\u043b B" if language == "ru" else "Signal B",
        "preview_ready": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0442\u0430\u0439\u043c\u0444\u0440\u0435\u0439\u043c" if language == "ru" else "Pick a timeframe",
        "preview_note": (
            "\u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 \u0441\u0438\u0433\u043d\u0430\u043b\u0430 \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u0445\u043e\u0434\u0430 \u043d\u0430 \u043f\u043e\u043b\u043d\u0443\u044e \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443."
            if language == "ru"
            else "Quick signal preview without leaving the lane."
        ),
        "level_waiting": "\u0416\u0434\u0451\u043c \u0443\u0440\u043e\u0432\u043d\u0438" if language == "ru" else "Waiting for levels",
        "level_waiting_note": "\u041d\u0443\u0436\u043d\u044b \u0432\u0445\u043e\u0434, \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f \u0438 \u0446\u0435\u043b\u044c." if language == "ru" else "Need entry, invalidation, and target.",
    }


def _workflow_state_label(state) -> str:
    value = getattr(state, "value", state)
    labels = {
        "watching": "watching",
        "validating": "validating",
        "ready": "ready",
        "ignored": "ignored",
        "escalate": "escalated",
        "resolved": "resolved",
    }
    return labels.get(value, str(value))
