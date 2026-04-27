from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp
from apps.api.routes.dashboard_tags import render_tag_chips


def render_journal_decision_log_item(item) -> str:
    signal = item.signal
    latest_entry = item.latest_entry
    why_now = "".join(f"<li>{escape(point)}</li>" for point in item.why_now)
    next_watch = "".join(f"<li>{escape(point)}</li>" for point in item.next_watch)
    latest_note = (
        f"Latest note: {escape(latest_entry.title)} | {escape(latest_entry.author)} | {escape(format_timestamp(latest_entry.created_at))}"
        if latest_entry is not None
        else f"Latest note: none yet | updated {escape(format_timestamp(item.updated_at))}"
    )
    return (
        '<article class="decision-card">'
        '<div class="decision-head">'
        f'<div><strong>{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</strong><p class="muted">{escape(signal.summary)}</p></div>'
        '<div class="decision-head-actions">'
        f'<span class="badge">{escape(signal.direction_final.value)} | {escape(signal.status.value)}</span>'
        f"{_render_workflow_chip(signal)}"
        "</div>"
        "</div>"
        '<div class="decision-grid">'
        f"<article><span>Decision</span><p>{escape(item.decision_summary)}</p></article>"
        f"<article><span>Why this is the current call</span><ul>{why_now}</ul></article>"
        f"<article><span>What should change next</span><ul>{next_watch}</ul></article>"
        "</div>"
        f'<p class="muted" style="margin-top:12px;">{latest_note}</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;">'
        f'<a class="button" href="/workspace/signals/{escape(signal.signal_id)}">Open signal page</a>'
        f'<a class="button" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Open in workspace</a>'
        "</div>"
        "</article>"
    )


def render_journal_workspace_entry(item) -> str:
    signal = item.signal
    entry = item.entry
    tags = render_tag_chips(getattr(entry, "tags", []))
    return (
        '<article class="entry-card">'
        '<div class="entry-meta">'
        f'<div><strong>{escape(entry.title)}</strong><p class="muted">{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</p></div>'
        f'<span class="badge">{escape(entry.kind.value)} | {escape(signal.status.value)}</span>'
        "</div>"
        f'<p class="muted">{escape(entry.note)}</p>'
        f"{tags}"
        f'<p class="muted">author {escape(entry.author)} | created {escape(format_timestamp(entry.created_at))}</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;">'
        f'<a class="button" href="/workspace/signals/{escape(signal.signal_id)}">Open signal page</a>'
        f'<a class="button" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Open in workspace</a>'
        "</div>"
        "</article>"
    )


def _render_workflow_chip(signal) -> str:
    state = getattr(signal, "workflow_state", "watching")
    tone = _workflow_state_tone(state)
    label = _workflow_state_label(state)
    return f'<span class="workflow-chip tone-{escape(tone)}">{escape(label)}</span>'


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


def _workflow_state_tone(state) -> str:
    value = getattr(state, "value", state)
    tones = {
        "watching": "watch",
        "validating": "review",
        "ready": "ready",
        "ignored": "ignore",
        "escalate": "escalate",
        "resolved": "resolved",
    }
    return tones.get(value, "watch")
