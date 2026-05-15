from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp
from apps.api.routes.dashboard_tags import render_tag_chips


def render_action_item(item) -> str:
    return (
        f'<article class="action-card tone-{escape(item.tone)}">'
        f"<strong>{escape(item.title)}</strong>"
        f'<p class="muted">{escape(item.detail)}</p>'
        "</article>"
    )


def render_journal_entry(entry) -> str:
    tags = render_tag_chips(getattr(entry, "tags", []))
    return (
        '<article class="journal-entry">'
        f"<strong>{escape(entry.title)}</strong>"
        f"<small>{escape(entry.kind.value)} | {escape(entry.author)} | {escape(format_timestamp(entry.created_at))}</small>"
        f'<p class="muted">{escape(entry.note)}</p>'
        f"{tags}"
        "</article>"
    )


def render_related_signal(signal) -> str:
    return (
        f'<a class="related-card" href="/workspace/signals/{escape(signal.signal_id)}">'
        f"<strong>{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</strong>"
        f'<p class="muted">{escape(signal.summary)}</p>'
        f'<p class="muted">confidence {signal.confidence_final:.2f} | skeptic {signal.skeptic_score:.2f} | {escape(signal.direction_final.value)} | workflow {_workflow_state_label(signal.workflow_state)}</p>'
        "</a>"
    )


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
