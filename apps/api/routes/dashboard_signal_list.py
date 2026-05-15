from __future__ import annotations

from html import escape


def render_signal_card(signal) -> str:
    return (
        '<article class="signal-card">'
        '<div class="signal-top">'
        f'<div><strong>{escape(signal.root)} · {escape(signal.contract)}</strong><div class="signal-summary">{escape(signal.summary)}</div></div>'
        f'<span class="badge">{escape(signal.direction_final.value)} · {escape(signal.horizon.value)}</span>'
        "</div>"
        '<div class="signal-meta">'
        f"<small>confidence {signal.confidence_final:.2f}</small>"
        f"<small>skeptic {signal.skeptic_score:.2f}</small>"
        f"<small>priority {signal.priority_score}</small>"
        f"<small>workflow {_workflow_state_label(signal.workflow_state)}</small>"
        "</div>"
        "</article>"
    )


def render_signal_row(signal) -> str:
    return (
        '<article class="signal-row">'
        f"<strong>{escape(signal.root)} · {escape(signal.horizon.value)} · {escape(signal.direction_final.value)}</strong>"
        f"<small>{escape(signal.summary)} | workflow {_workflow_state_label(signal.workflow_state)}</small>"
        "</article>"
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
