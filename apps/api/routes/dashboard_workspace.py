from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_price_value, format_signed_pct


def render_market_freshness_alerts(alerts, *, language: str) -> str:
    items = list(alerts or [])
    if not items:
        return ""

    copy = _market_freshness_alert_copy(language)
    cards = "".join(_render_market_freshness_alert(item, copy=copy) for item in items)
    return (
        '<section class="panel market-freshness-alerts" data-market-freshness-alerts>'
        '<div class="panel-head">'
        "<div>"
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        f'<span class="filter-chip is-active">{len(items)} {escape(copy["count_label"])}</span>'
        "</div>"
        f'<div class="summary-grid">{cards}</div>'
        "</section>"
    )


def _render_market_freshness_alert(alert, *, copy: dict[str, object]) -> str:
    localized_items = copy.get("items", {})
    item_copy = localized_items.get(alert.key, {}) if isinstance(localized_items, dict) else {}
    title = str(item_copy.get("title", alert.title))
    detail = str(item_copy.get("detail", alert.detail))
    status_labels = copy.get("status_labels", {})
    status_label = (
        str(status_labels.get(alert.status, alert.status)) if isinstance(status_labels, dict) else alert.status
    )
    raw_detail = str(alert.detail)
    dynamic_detail = f'<small>{escape(raw_detail)}</small>' if raw_detail and raw_detail != detail else ""
    return (
        f'<article class="decision-card tone-{escape(alert.tone)}" data-market-freshness-alert '
        f'data-market-freshness-key="{escape(alert.key)}" '
        f'data-market-freshness-status="{escape(alert.status)}" '
        f'data-market-freshness-root="{escape(alert.root_code)}">'
        f'<span>{escape(status_label)}</span>'
        f'<strong>{escape(title)}</strong>'
        f'<p>{escape(detail)}</p>'
        f"{dynamic_detail}"
        '<div class="metric-row">'
        f'<small>{escape(copy["signals_only"])}</small>'
        f'<small>{escape(copy["root_label"])} {escape(alert.root_code)}</small>'
        "</div>"
        '<div class="card-actions">'
        f'<a class="button" href="{escape(alert.href)}">{escape(copy["action"])}</a>'
        "</div>"
        "</article>"
    )


def render_morning_brief(snapshot, *, language: str) -> str:
    copy = _morning_brief_copy(language)
    brief = getattr(snapshot, "morning_brief", None)
    if brief is not None:
        market_status = brief.market_status or copy["market_hidden"]
        market_detail = brief.market_detail or (
            copy["market_ready_detail"] if market_status == "fresh" else copy["market_hidden_detail"]
        )
        price_line = copy["price_hidden"]
        if brief.last_price is not None:
            unit = f" {escape(brief.price_unit or '')}".rstrip()
            price_line = f"{format_price_value(brief.last_price)}{unit}"
        top_attention = list(brief.top_attention or [])
        stale_or_degraded = list(brief.dont_chase or [])
        highlights = list(brief.review_highlights or [])
        review_due = brief.review_due_items
        watched_roots = list(brief.watched_roots or [])
        delivery_ready = brief.telegram_status == "ready"
        data_mode = brief.data_mode
    else:
        market_snapshot = getattr(snapshot, "market_snapshot", None)
        market_status = getattr(market_snapshot, "status", None) or copy["market_hidden"]
        market_detail = (
            getattr(market_snapshot, "status_detail", None)
            or (
                copy["market_ready_detail"]
                if market_snapshot is not None and market_status == "fresh"
                else copy["market_hidden_detail"]
            )
        )
        price_line = copy["price_hidden"]
        if market_snapshot is not None:
            unit = f" {escape(getattr(market_snapshot, 'unit', '') or '')}".rstrip()
            price_line = f"{format_price_value(market_snapshot.current_price)}{unit}"
        attention_items = list(getattr(snapshot, "attention_inbox", []) or [])
        top_attention = attention_items[:3]
        stale_or_degraded = [
            item
            for item in attention_items
            if str(getattr(item, "market_status", "")).lower() not in {"fresh", "live"}
        ][:3]
        review_bundle = getattr(snapshot, "review_bundle", None)
        highlights = list(getattr(review_bundle, "highlights", []) or [])
        if not highlights:
            highlights = list(getattr(review_bundle, "outcome_summary", []) or [])
        review_due = getattr(review_bundle, "review_due_items", 0) if review_bundle is not None else 0
        watched_roots = getattr(review_bundle, "watched_root_codes", []) if review_bundle is not None else []
        delivery_ready = bool(getattr(snapshot, "telegram_delivery_ready", False))
        data_mode = snapshot.control_panel.data_mode

    attention_count = len(getattr(snapshot, "attention_inbox", []) or top_attention)
    review_bundle = getattr(snapshot, "review_bundle", None)
    attention_lines = (
        "".join(
            f'<li><a href="{escape(getattr(item, "href", None) or "#")}">{escape(item.title)}</a>'
            f'<span>{escape(_morning_brief_attention_detail(item))}</span></li>'
            for item in top_attention
        )
        or f'<li><span>{escape(copy["attention_empty"])}</span></li>'
    )
    dont_chase_lines = (
        "".join(
            f'<li><strong>{escape(item.title)}</strong><span>{escape(_morning_brief_caution_detail(item))}</span></li>'
            for item in stale_or_degraded
        )
        or f'<li><span>{escape(copy["dont_chase_empty"])}</span></li>'
    )

    if not highlights:
        highlights = [copy["delta_empty"]]
    delta_lines = "".join(f"<li>{escape(item)}</li>" for item in highlights[:3])
    watched_label = ", ".join(watched_roots[:4]) if watched_roots else copy["none"]

    return (
        '<section class="panel morning-brief" data-morning-brief>'
        '<div class="panel-head">'
        "<div>"
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        f'<span class="filter-chip is-active">{escape(copy["signals_only"])}</span>'
        "</div>"
        '<div class="summary-grid">'
        '<article class="decision-card tone-neutral" data-morning-brief-market>'
        f'<span>{escape(copy["market_truth"])}</span><strong>{escape(market_status)}</strong>'
        f'<p>{escape(market_detail)}</p><small>{escape(copy["last_price"])} {price_line}</small>'
        "</article>"
        '<article class="decision-card tone-positive" data-morning-brief-attention>'
        f'<span>{escape(copy["attention"])}</span><strong>{attention_count}</strong>'
        f"<ul>{attention_lines}</ul>"
        "</article>"
        '<article class="decision-card tone-neutral" data-morning-brief-delta>'
        f'<span>{escape(copy["overnight_delta"])}</span><strong>{escape(copy["review_ready"])}</strong>'
        f"<ul>{delta_lines}</ul>"
        "</article>"
        '<article class="decision-card tone-warning" data-morning-brief-dont-chase>'
        f'<span>{escape(copy["dont_chase"])}</span><strong>{len(stale_or_degraded)}</strong>'
        f"<ul>{dont_chase_lines}</ul>"
        "</article>"
        "</div>"
        '<div class="metric-row">'
        f'<small>{escape(copy["review_due"])} {review_due}</small>'
        f'<small>{escape(copy["watched_roots"])} {escape(watched_label)}</small>'
        f'<small>{escape(copy["delivery"])} {escape(copy["ready"] if delivery_ready else copy["preview_only"])}</small>'
        f'<small>{escape(copy["data_mode"])} {escape(data_mode)}</small>'
        "</div>"
        "</section>"
    )


def render_readiness_next_steps(snapshot, *, language: str) -> str:
    copy = _readiness_next_steps_copy(language)
    readiness = getattr(snapshot, "readiness_next_steps", None)
    if readiness is None:
        return ""

    items = list(getattr(readiness, "items", []) or [])
    cards = (
        "".join(_render_readiness_next_step_item(item, copy=copy) for item in items)
        or f'<p class="empty">{escape(copy["empty"])}</p>'
    )
    status_text = copy["ready"] if readiness.open_items == 0 else f'{readiness.open_items} {copy["open"]}'
    return (
        '<section class="panel readiness-next-steps" data-readiness-next-steps>'
        '<div class="panel-head">'
        "<div>"
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        f'<span class="filter-chip is-active">{escape(status_text)}</span>'
        "</div>"
        f'<div class="summary-grid">{cards}</div>'
        '<div class="metric-row">'
        f'<small>{escape(copy["signals_only"])}</small>'
        f'<small>{escape(copy["ready_label"])} {readiness.ready_items}</small>'
        f'<small>{escape(copy["open_label"])} {readiness.open_items}</small>'
        f'<small>{escape(copy["next_step"])} {escape(readiness.next_step)}</small>'
        "</div>"
        "</section>"
    )


def _render_readiness_next_step_item(item, *, copy: dict[str, object]) -> str:
    localized_items = copy.get("items", {})
    item_copy = localized_items.get(item.key, {}) if isinstance(localized_items, dict) else {}
    title = str(item_copy.get("title", item.title))
    detail = str(item_copy.get(f"detail_{item.status}", item_copy.get("detail", item.detail)))
    status_labels = copy.get("status_labels", {})
    status_label = str(status_labels.get(item.status, item.status)) if isinstance(status_labels, dict) else item.status
    action_label = str(copy["action"])
    raw_detail = str(item.detail)
    dynamic_detail = f'<small>{escape(raw_detail)}</small>' if raw_detail and raw_detail != detail else ""
    return (
        f'<article class="decision-card tone-{escape(item.tone)}" data-readiness-gap '
        f'data-readiness-gap-key="{escape(item.key)}" '
        f'data-readiness-gap-status="{escape(item.status)}">'
        f'<span>{escape(status_label)}</span>'
        f'<strong>{escape(title)}</strong>'
        f'<p>{escape(detail)}</p>'
        f"{dynamic_detail}"
        '<div class="card-actions">'
        f'<a class="button" href="{escape(item.href)}">{escape(action_label)}</a>'
        "</div>"
        "</article>"
    )


def render_attention_inbox(items, *, language: str) -> str:
    copy = _attention_inbox_copy(language)
    if not items:
        cards = f'<p class="empty">{escape(copy["empty"])}</p>'
    else:
        cards = "".join(_render_attention_card(item, copy=copy) for item in items)
    return (
        '<section class="panel attention-inbox" data-attention-inbox>'
        '<div class="panel-head">'
        "<div>"
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        f'<span class="filter-chip is-active">{len(items)} {escape(copy["count_label"])}</span>'
        "</div>"
        f'<div class="attention-grid">{cards}</div>'
        "</section>"
    )


def _render_attention_card(item, *, copy: dict[str, str]) -> str:
    workflow = _workflow_state_label(item.workflow_state) if item.workflow_state is not None else copy["root_item"]
    unit = f" {escape(item.price_unit)}" if item.price_unit else ""
    price = (
        f"{format_price_value(item.current_price)}{unit}"
        if item.current_price is not None
        else copy["price_hidden"]
    )
    signal_link = (
        f'<a class="button" href="/workspace/signals/{escape(item.signal_id)}">{escape(copy["details"])}</a>'
        if item.signal_id
        else ""
    )
    detail = f'<small>{escape(item.market_status_detail)}</small>' if item.market_status_detail else ""
    return (
        f'<article class="decision-card tone-{escape(item.tone)}" data-attention-card '
        f'data-attention-item-key="{escape(item.item_key)}" '
        f'data-attention-root-code="{escape(item.root_code)}" '
        f'data-attention-signal-id="{escape(item.signal_id or "")}">'
        '<div class="signal-top">'
        f'<div><strong>{escape(item.title)}</strong><p class="muted">{escape(item.reason)}</p></div>'
        f'<span class="badge">{escape(copy["score"])} {item.attention_score:.0f}</span>'
        "</div>"
        '<div class="metric-row">'
        f'<small>{escape(copy["price"])} {price}</small>'
        f'<small>{escape(copy["status"])} {escape(item.market_status)}</small>'
        f'<small>{escape(copy["priority"])} {item.priority_score}</small>'
        f'<small>{escape(copy["workflow"])} {escape(workflow)}</small>'
        "</div>"
        f'<p><strong>{escape(copy["changed"])}</strong> {escape(item.what_changed)}</p>'
        f'<p><strong>{escape(copy["next_step"])}</strong> {escape(item.next_step)}</p>'
        f'<p class="muted">{detail}</p>'
        '<div class="card-actions">'
        f'<a class="button primary" href="{escape(item.href)}">{escape(copy["focus"])}</a>'
        f"{signal_link}"
        "</div>"
        "</article>"
    )


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


def _attention_inbox_copy(language: str) -> dict[str, str]:
    if language == "ru":
        return {
            "title": "\u0422\u0440\u0435\u0431\u0443\u0435\u0442 \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f \u0441\u0435\u0439\u0447\u0430\u0441",
            "subtitle": "\u041b\u0438\u0447\u043d\u0430\u044f \u043e\u0447\u0435\u0440\u0435\u0434\u044c: \u0441\u0438\u0433\u043d\u0430\u043b\u044b \u0438 \u0441\u0435\u0440\u0438\u0438, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u0441\u0442\u043e\u0438\u0442 \u0440\u0430\u0437\u043e\u0431\u0440\u0430\u0442\u044c \u043f\u0435\u0440\u0432\u044b\u043c\u0438.",
            "count_label": "\u0432 \u043e\u0447\u0435\u0440\u0435\u0434\u0438",
            "score": "\u0412\u043d\u0438\u043c\u0430\u043d\u0438\u0435",
            "price": "\u0426\u0435\u043d\u0430",
            "status": "\u0414\u0430\u043d\u043d\u044b\u0435",
            "priority": "\u041f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442",
            "workflow": "\u0421\u0442\u0430\u0442\u0443\u0441",
            "changed": "\u0427\u0442\u043e \u0438\u0437\u043c\u0435\u043d\u0438\u043b\u043e\u0441\u044c:",
            "next_step": "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0448\u0430\u0433:",
            "focus": "\u0412 \u0444\u043e\u043a\u0443\u0441",
            "details": "\u0414\u0435\u0442\u0430\u043b\u0438",
            "price_hidden": "\u0441\u043a\u0440\u044b\u0442\u0430",
            "root_item": "\u0441\u0435\u0440\u0438\u044f",
            "empty": "\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442\u043e\u0432 \u043d\u0430 \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u0435.",
        }
    return {
        "title": "Needs attention now",
        "subtitle": "A personal queue of signals and roots to review first.",
        "count_label": "queued",
        "score": "Attention",
        "price": "Price",
        "status": "Data",
        "priority": "Priority",
        "workflow": "Workflow",
        "changed": "What changed:",
        "next_step": "Next step:",
        "focus": "Focus",
        "details": "Details",
        "price_hidden": "hidden",
        "root_item": "root",
        "empty": "No active attention candidates yet.",
    }


def _market_freshness_alert_copy(language: str) -> dict[str, object]:
    if language == "ru":
        return {
            "title": "\u0410\u043b\u0435\u0440\u0442\u044b \u0441\u0432\u0435\u0436\u0435\u0441\u0442\u0438 market data",
            "subtitle": "\u0412\u0438\u0434\u043d\u044b \u0442\u043e\u043b\u044c\u043a\u043e, \u043a\u043e\u0433\u0434\u0430 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0439 \u0441\u0435\u0440\u0438\u0438 \u043d\u0443\u0436\u043d\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 feed.",
            "count_label": "\u0430\u043b\u0435\u0440\u0442",
            "signals_only": "signals-only",
            "root_label": "\u0421\u0435\u0440\u0438\u044f:",
            "action": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c evidence",
            "status_labels": {
                "hidden": "\u0441\u043a\u0440\u044b\u0442\u043e",
                "stale": "stale",
                "degraded": "degraded",
                "degraded_feed": "degraded feed",
                "aging": "aging",
                "unknown": "unknown",
            },
            "items": {
                "market_data_hidden": {
                    "title": "\u0414\u0430\u043d\u043d\u044b\u0435 \u0441\u043a\u0440\u044b\u0442\u044b",
                    "detail": "\u0426\u0435\u043d\u0430 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b, \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0442\u0440\u0430\u0441\u0441\u0438\u0440\u0443\u0435\u043c\u043e\u0433\u043e \u0441\u043d\u0438\u043c\u043a\u0430.",
                },
                "market_data_not_fresh": {
                    "title": "Feed \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438",
                    "detail": "\u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0441\u0432\u0435\u0436\u0435\u0441\u0442\u044c \u0446\u0435\u043d\u044b \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u043e\u0432 \u043f\u0435\u0440\u0435\u0434 \u0440\u0430\u0437\u0431\u043e\u0440\u043e\u043c \u0441\u0435\u0442\u0430\u043f\u0430.",
                },
                "runtime_data_mode_degraded": {
                    "title": "\u0420\u0435\u0436\u0438\u043c \u0434\u0430\u043d\u043d\u044b\u0445 degraded",
                    "detail": "\u041e\u0441\u043d\u043e\u0432\u043d\u043e\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0446\u0435\u043d\u044b \u0434\u0435\u0433\u0440\u0430\u0434\u0438\u0440\u043e\u0432\u0430\u043b \u0438\u043b\u0438 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d.",
                },
            },
        }
    return {
        "title": "Market Freshness Alerts",
        "subtitle": "Shown only when the selected root needs feed review.",
        "count_label": "alert",
        "signals_only": "signals-only",
        "root_label": "Root:",
        "action": "Open evidence",
        "status_labels": {},
        "items": {},
    }


def _readiness_next_steps_copy(language: str) -> dict[str, object]:
    if language == "ru":
        return {
            "title": "\u0427\u0442\u043e \u0435\u0449\u0451 \u0437\u0430\u043a\u0440\u044b\u0442\u044c",
            "subtitle": "\u041a\u043e\u0440\u043e\u0442\u043a\u0438\u0439 readiness-\u0441\u0440\u0435\u0437 \u043f\u0435\u0440\u0435\u0434 private-beta \u0440\u0435\u0448\u0435\u043d\u0438\u0435\u043c.",
            "signals_only": "signals-only",
            "ready_label": "\u0413\u043e\u0442\u043e\u0432\u043e:",
            "open_label": "\u041e\u0442\u043a\u0440\u044b\u0442\u043e:",
            "next_step": "\u0428\u0430\u0433:",
            "ready": "\u0433\u043e\u0442\u043e\u0432\u043e",
            "open": "\u043e\u0442\u043a\u0440\u044b\u0442\u043e",
            "empty": "\u041d\u0435\u0442 readiness-\u043f\u0443\u043d\u043a\u0442\u043e\u0432.",
            "action": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c",
            "status_labels": {
                "ready": "\u0433\u043e\u0442\u043e\u0432\u043e",
                "review": "\u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c",
                "open": "\u043e\u0442\u043a\u0440\u044b\u0442\u043e",
                "blocked": "\u0431\u043b\u043e\u043a\u0435\u0440",
            },
            "items": {
                "market_data_truth": {
                    "title": "\u0427\u0435\u0441\u0442\u043d\u043e\u0441\u0442\u044c market data",
                    "detail_blocked": "\u0426\u0435\u043d\u044b \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b, \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0442\u0440\u0430\u0441\u0441\u0438\u0440\u0443\u0435\u043c\u043e\u0433\u043e feed.",
                    "detail_review": "\u0421\u0442\u0430\u0442\u0443\u0441 feed \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u043f\u0435\u0440\u0435\u0434 acceptance.",
                    "detail_ready": "\u0426\u0435\u043d\u0430 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0432\u0438\u0434\u043d\u044b \u0441 \u0447\u0435\u0441\u0442\u043d\u044b\u043c feed-\u0441\u0442\u0430\u0442\u0443\u0441\u043e\u043c.",
                },
                "telegram_mode": {
                    "title": "\u0420\u0435\u0436\u0438\u043c Telegram",
                    "detail_review": "Preview \u0433\u043e\u0442\u043e\u0432; \u0432\u043a\u043b\u044e\u0447\u0430\u0442\u044c delivery \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u043e \u044f\u0432\u043d\u043e\u043c\u0443 \u0440\u0435\u0448\u0435\u043d\u0438\u044e \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0430.",
                    "detail_ready": "\u041f\u0440\u0438\u043a\u0440\u0435\u043f\u0438\u0442\u0435 preview-\u0434\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u043e \u0438 \u0440\u0435\u0436\u0438\u043c \u0432 release notes.",
                },
                "daily_review": {
                    "title": "\u0414\u043d\u0435\u0432\u043d\u0430\u044f \u043e\u0447\u0435\u0440\u0435\u0434\u044c",
                    "detail_open": "\u041e\u0447\u0435\u0440\u0435\u0434\u044c \u0435\u0449\u0451 \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u0440\u0435\u0432\u044c\u044e \u043f\u0435\u0440\u0435\u0434 \u0444\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u043c\u0438 notes.",
                    "detail_ready": "Today's Operating Queue \u0431\u0435\u0437 overdue \u043f\u0443\u043d\u043a\u0442\u043e\u0432.",
                },
                "delivery_reason_trails": {
                    "title": "\u0421\u043b\u0435\u0434\u044b delivery-\u0440\u0435\u0448\u0435\u043d\u0438\u0439",
                    "detail_review": "\u0414\u043e\u0431\u0430\u0432\u044c\u0442\u0435 preview, dry-run, skip \u0438\u043b\u0438 suppression evidence \u0434\u043e acceptance review.",
                    "detail_ready": "\u041d\u0435\u0434\u0430\u0432\u043d\u044f\u044f delivery-\u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c \u0438\u043c\u0435\u0435\u0442 \u043e\u0431\u044a\u044f\u0441\u043d\u0438\u043c\u044b\u0435 reason trails.",
                },
            },
        }
    return {
        "title": "Readiness Next Steps",
        "subtitle": "A short private-beta readiness slice before any acceptance decision.",
        "signals_only": "signals-only",
        "ready_label": "Ready:",
        "open_label": "Open:",
        "next_step": "Step:",
        "ready": "ready",
        "open": "open",
        "empty": "No readiness items yet.",
        "action": "Open",
        "status_labels": {
            "ready": "ready",
            "review": "review",
            "open": "open",
            "blocked": "blocker",
        },
        "items": {},
    }


def _morning_brief_copy(language: str) -> dict[str, str]:
    if language == "ru":
        return {
            "title": "\u0423\u0442\u0440\u0435\u043d\u043d\u0438\u0439 \u0431\u0440\u0438\u0444",
            "subtitle": "\u0427\u0442\u043e \u0438\u0437\u043c\u0435\u043d\u0438\u043b\u043e\u0441\u044c, \u0447\u0442\u043e \u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u043f\u0435\u0440\u0432\u044b\u043c \u0438 \u0447\u0442\u043e \u043d\u0435 \u0433\u043d\u0430\u0442\u044c \u0431\u0435\u0437 \u0434\u043e\u0432\u0435\u0440\u0438\u044f \u043a \u0434\u0430\u043d\u043d\u044b\u043c.",
            "signals_only": "signals-only",
            "market_truth": "\u0414\u0430\u043d\u043d\u044b\u0435",
            "market_hidden": "\u0441\u043a\u0440\u044b\u0442\u044b",
            "market_ready_detail": "\u0426\u0435\u043d\u0430 \u0438 \u0441\u0432\u0435\u0447\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b.",
            "market_hidden_detail": "\u0426\u0435\u043d\u0430 \u0438\u043b\u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0447\u0435\u0441\u0442\u043d\u043e \u0441\u043a\u0440\u044b\u0442\u044b.",
            "price_hidden": "\u0441\u043a\u0440\u044b\u0442\u0430",
            "last_price": "\u0426\u0435\u043d\u0430:",
            "attention": "\u0422\u043e\u043f \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f",
            "attention_empty": "\u041d\u0435\u0442 \u0441\u0440\u043e\u0447\u043d\u044b\u0445 \u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442\u043e\u0432.",
            "overnight_delta": "\u0414\u0435\u043b\u044c\u0442\u0430",
            "review_ready": "\u0433\u043e\u0442\u043e\u0432\u043e",
            "delta_empty": "\u041d\u043e\u0432\u044b\u0445 \u0438\u0442\u043e\u0433\u043e\u0432 \u0440\u0435\u0432\u044c\u044e \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.",
            "dont_chase": "\u041d\u0435 \u0433\u043d\u0430\u0442\u044c",
            "dont_chase_empty": "\u041d\u0435\u0442 stale/degraded \u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442\u043e\u0432 \u0432 \u0442\u043e\u043f\u0435.",
            "review_due": "\u041a \u0440\u0435\u0432\u044c\u044e:",
            "watched_roots": "\u041a\u043e\u0440\u043d\u0438:",
            "delivery": "Telegram:",
            "ready": "\u0433\u043e\u0442\u043e\u0432",
            "preview_only": "preview",
            "data_mode": "\u0420\u0435\u0436\u0438\u043c:",
            "none": "\u043d\u0435\u0442",
        }
    return {
        "title": "Morning Command Brief",
        "subtitle": "What changed, what to review first, and what not to chase without trustworthy data.",
        "signals_only": "signals-only",
        "market_truth": "Market truth",
        "market_hidden": "hidden",
        "market_ready_detail": "Price and candles are available for the selected instrument.",
        "market_hidden_detail": "Price or chart data is honestly hidden until the feed is usable.",
        "price_hidden": "hidden",
        "last_price": "Last:",
        "attention": "Top attention",
        "attention_empty": "No urgent candidates are queued.",
        "overnight_delta": "Overnight delta",
        "review_ready": "ready",
        "delta_empty": "No new review highlights yet.",
        "dont_chase": "Don't chase",
        "dont_chase_empty": "No stale or degraded top candidates.",
        "review_due": "Review due:",
        "watched_roots": "Watched roots:",
        "delivery": "Telegram:",
        "ready": "ready",
        "preview_only": "preview",
        "data_mode": "Data mode:",
        "none": "none",
    }


def _morning_brief_attention_detail(item) -> str:
    return str(getattr(item, "detail", None) or getattr(item, "reason", ""))


def _morning_brief_caution_detail(item) -> str:
    detail = getattr(item, "detail", None)
    if detail:
        return str(detail)
    status = str(getattr(item, "market_status", "unknown"))
    status_detail = getattr(item, "market_status_detail", None)
    return f"{status}: {status_detail}" if status_detail else status


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
