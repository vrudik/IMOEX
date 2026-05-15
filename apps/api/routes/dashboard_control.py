from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp


def control_panel_data_mode_tone(mode: str) -> str:
    if mode == "live":
        return "tone-positive"
    if mode == "snapshot":
        return "tone-warning"
    return "tone-negative"


def control_panel_data_mode_label(mode: str) -> str:
    labels = {
        "live": "Live",
        "snapshot": "Snapshot",
        "degraded_feed": "Degraded feed",
    }
    return labels.get(mode, mode.replace("_", " ").title())


def control_panel_reference_sync_tone(status: str) -> str:
    if status == "fresh":
        return "tone-positive"
    if status == "stale":
        return "tone-warning"
    return "tone-negative"


def control_panel_reference_sync_label(status: str) -> str:
    labels = {
        "fresh": "Fresh",
        "stale": "Stale",
        "fallback": "Fallback",
    }
    return labels.get(status, status.replace("_", " ").title())


def control_panel_reference_sync_source(source: str) -> str:
    labels = {
        "moex_iss": "MOEX ISS",
        "bundled_fallback": "Bundled fallback",
    }
    return labels.get(source, source.replace("_", " ").title())


def primary_market_feed(panel):
    primary = next((item for item in panel.market_data_feeds if item.primary), None)
    if primary is not None:
        return primary
    return panel.market_data_feeds[0] if panel.market_data_feeds else None


def runtime_prompt_approval_state_label(state: str, copy: dict[str, str]) -> str:
    mapping = {
        "live": copy["approval_state_live"],
        "approved": copy["approval_state_approved"],
        "pending_approval": copy["approval_state_pending"],
    }
    return str(mapping.get(state, state.replace("_", " ").title()))


def runtime_prompt_default_version_id(item: object) -> str:
    return f"default:{getattr(item, 'role_key')}"


def runtime_prompt_effective_template(item: object) -> str:
    return str(getattr(item, "effective_prompt_template", None) or getattr(item, "prompt_template"))


def runtime_prompt_effective_rendered_prompt(item: object) -> str:
    return str(getattr(item, "effective_rendered_prompt", None) or runtime_prompt_effective_template(item))


def runtime_prompt_working_rendered_prompt(item: object) -> str:
    return str(getattr(item, "rendered_prompt", None) or getattr(item, "prompt_template"))


def render_runtime_prompt_history_entry(
    item: object,
    *,
    role_key: str,
    current_version_id: str | None,
    approved_version_id: str | None,
    pending_version_id: str | None,
    copy: dict[str, str],
) -> str:
    badges: list[str] = []
    version_id = getattr(item, "version_id", None)
    if version_id == approved_version_id:
        badges.append(f'<span class="badge prompt-current-badge">{escape(copy["approved_version"])}</span>')
    if version_id == pending_version_id:
        badges.append(f'<span class="badge prompt-pending-badge">{escape(copy["pending_version"])}</span>')
    elif version_id == current_version_id:
        badges.append(f'<span class="badge prompt-current-badge">{escape(copy["current_version"])}</span>')
    restored_note = ""
    restored_from_version_id = getattr(item, "restored_from_version_id", None)
    if restored_from_version_id:
        restored_note = (
            f'<p class="muted">{escape(copy["restored_from"])} '
            f"{escape(restored_from_version_id)}</p>"
        )
    version_state = str(getattr(item, "lifecycle_state", "superseded"))
    version_state_label = escape(copy.get(f"version_state_{version_state}", version_state.replace("_", " ").title()))
    badges.append(f'<span class="badge" data-runtime-prompt-version-state>{version_state_label}</span>')
    release_note_markup = (
        f'<p class="muted" data-runtime-prompt-release-note>{escape(copy["release_note"])}: '
        f'{escape(getattr(item, "release_note"))}</p>'
        if getattr(item, "release_note", None)
        else ""
    )
    restore_button = (
        f'<button class="button" type="button" data-runtime-prompt-restore '
        f'data-role-key="{escape(role_key)}" data-version-id="{escape(getattr(item, "version_id"))}">'
        f'{escape(copy["restore"])}</button>'
        if getattr(item, "restorable", True)
        else ""
    )
    return (
        '<article class="prompt-version" data-runtime-prompt-version>'
        f'<div class="route-head"><div><strong>{escape(getattr(item, "summary"))}</strong>'
        f'<p class="muted">{escape(getattr(item, "action"))} · '
        f'{escape(format_timestamp(getattr(item, "created_at")))}</p></div>'
        f'{"".join(badges)}</div>'
        f"{restored_note}"
        f"{release_note_markup}"
        f'<div class="prompt-version-actions">{restore_button}</div>'
        "</article>"
    )


def render_runtime_prompt_history(item: object, *, copy: dict[str, str]) -> str:
    default_version_id = runtime_prompt_default_version_id(item)
    history_cards = "".join(
        render_runtime_prompt_history_entry(
            version,
            role_key=getattr(item, "role_key"),
            current_version_id=getattr(item, "current_version_id", None),
            approved_version_id=getattr(item, "approved_version_id", None),
            pending_version_id=getattr(item, "pending_version_id", None),
            copy=copy,
        )
        for version in getattr(item, "version_history", [])
    )
    if not history_cards:
        history_cards = f'<p class="empty">{escape(copy["history_empty"])}</p>'
    return (
        f'<section class="prompt-history" data-runtime-prompt-history>'
        f'<div class="panel-head"><h3>{escape(copy["history"])}</h3>'
        f'<button class="button" type="button" data-runtime-prompt-restore '
        f'data-role-key="{escape(getattr(item, "role_key"))}" '
        f'data-version-id="{escape(default_version_id)}">'
        f'{escape(copy["restore_default"])}</button></div>'
        f'<p class="panel-note">{escape(copy["default_available"])}</p>'
        '<div data-runtime-prompt-version-state hidden></div>'
        '<div data-runtime-prompt-release-note hidden></div>'
        f"{history_cards}"
        "</section>"
    )


def render_market_data_context(panel) -> str:
    primary_feed = primary_market_feed(panel)
    if primary_feed is None:
        return (
            "<article><span>Price Source</span><strong>n/a</strong>"
            '<p class="muted">No market-data feed is attached yet.</p></article>'
        )

    data_mode_label = control_panel_data_mode_label(panel.data_mode)
    updated_at = format_timestamp(primary_feed.last_update_at)
    return (
        f"<article><span>Price Source</span><strong>{escape(primary_feed.owner)}</strong>"
        f'<p class="muted">{escape(data_mode_label)} | Updated {escape(updated_at)}</p></article>'
    )


def render_control_panel(panel) -> str:
    latest_market_data = format_timestamp(panel.latest_market_data_at)
    data_mode_label = control_panel_data_mode_label(panel.data_mode)
    data_mode_tone = control_panel_data_mode_tone(panel.data_mode)
    data_mode_detail = escape(panel.data_mode_detail or "No detail available.")
    reference_sync_label = control_panel_reference_sync_label(panel.reference_sync.status)
    reference_sync_source = control_panel_reference_sync_source(panel.reference_sync.source)
    reference_sync_tone = control_panel_reference_sync_tone(panel.reference_sync.status)
    reference_sync_detail = escape(panel.reference_sync.detail or "No detail available.")
    latest_reference_sync = format_timestamp(panel.reference_sync.last_sync_at)
    role_cards = "".join(
        (
            "<article>"
            f"<strong>{escape(item.role_label)}</strong>"
            f"<p>{escape(item.product)} &middot; {escape(item.model)} &middot; {escape(item.owner)}</p>"
            f'<p class="muted">{escape(item.detail or item.control_mode)}</p>'
            "</article>"
        )
        for item in panel.model_roles
    ) or '<p class="empty">No model roles configured yet.</p>'
    feed_cards = "".join(
        (
            "<article>"
            f"<strong>{escape(item.provider)} &middot; {escape(item.owner)}</strong>"
            f"<p>{escape(item.role)} &middot; {escape(item.status)} &middot; last {escape(format_timestamp(item.last_update_at))}</p>"
            f'<p class="muted">{escape(item.detail or "No detail available.")}</p>'
            "</article>"
        )
        for item in panel.market_data_feeds
    ) or '<p class="empty">No market-data feeds are attached to this root yet.</p>'
    return (
        '<div class="control-summary-grid">'
        f'<article class="control-summary-card"><label>LLM runtime</label><strong>{escape(panel.llm_product)} &middot; {escape(panel.llm_model)}</strong></article>'
        f'<article class="control-summary-card"><label>LLM owner</label><strong>{escape(panel.llm_owner)}</strong></article>'
        f'<article class="control-summary-card is-wide {data_mode_tone}"><label>Data mode</label><strong>{escape(data_mode_label)}</strong><small>{data_mode_detail}</small></article>'
        f'<article class="control-summary-card"><label>Latest market data</label><strong>{escape(latest_market_data)}</strong></article>'
        f'<article class="control-summary-card is-wide {reference_sync_tone}"><label>Reference sync</label><strong>{escape(reference_sync_label)} &middot; {escape(reference_sync_source)}</strong><small>{escape(panel.reference_sync.owner)} | {reference_sync_detail}</small></article>'
        f'<article class="control-summary-card"><label>Latest reference sync</label><strong>{escape(latest_reference_sync)}</strong></article>'
        "</div>"
        '<div class="panel-head" style="margin-top:18px;"><h3>Role routing</h3></div>'
        f'<div class="metric-list">{role_cards}</div>'
        '<div class="panel-head" style="margin-top:18px;"><h3>Market-data feeds</h3></div>'
        f'<div class="metric-list">{feed_cards}</div>'
    )
