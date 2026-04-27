from __future__ import annotations

from html import escape

from libs.domain.contracts import SignalWorkflowState


def workflow_state_label(state: SignalWorkflowState) -> str:
    labels = {
        SignalWorkflowState.WATCHING: "watching",
        SignalWorkflowState.VALIDATING: "validating",
        SignalWorkflowState.READY: "ready",
        SignalWorkflowState.IGNORED: "ignored",
        SignalWorkflowState.ESCALATE: "escalated",
        SignalWorkflowState.RESOLVED: "resolved",
    }
    return labels.get(state, state.value)


def workflow_state_tone(state: SignalWorkflowState) -> str:
    tones = {
        SignalWorkflowState.WATCHING: "watch",
        SignalWorkflowState.VALIDATING: "review",
        SignalWorkflowState.READY: "ready",
        SignalWorkflowState.IGNORED: "ignore",
        SignalWorkflowState.ESCALATE: "escalate",
        SignalWorkflowState.RESOLVED: "resolved",
    }
    return tones.get(state, "watch")


def workflow_state_hint(state: SignalWorkflowState) -> str:
    hints = {
        SignalWorkflowState.WATCHING: "Keep this setup in view and wait for stronger confirmation.",
        SignalWorkflowState.VALIDATING: "Manually verify the setup before taking action.",
        SignalWorkflowState.READY: "The setup is actionable; manage it closely.",
        SignalWorkflowState.IGNORED: "This signal is deprioritized until the context changes.",
        SignalWorkflowState.ESCALATE: "This signal needs a higher-attention review right now.",
        SignalWorkflowState.RESOLVED: "The setup is closed and should now feed the review loop.",
    }
    return hints.get(state, "Manual workflow state for the current signal.")


def render_workflow_chip(signal) -> str:
    state = getattr(signal, "workflow_state", SignalWorkflowState.WATCHING)
    tone = workflow_state_tone(state)
    label = workflow_state_label(state)
    return f'<span class="workflow-chip tone-{escape(tone)}">{escape(label)}</span>'


def render_workflow_panel(signal, *, status_id: str) -> str:
    if signal is None:
        buttons = "".join(
            f'<button class="workflow-button tone-{escape(workflow_state_tone(state))}" type="button" disabled>{escape(workflow_state_label(state))}</button>'
            for state in SignalWorkflowState
        )
        return (
            '<div class="workflow-panel">'
            '<div class="workflow-meta">'
            "<div><span>Workflow</span><strong>Pick a signal first</strong></div>"
            "</div>"
            '<p class="workflow-summary">Select a signal to set how you want to handle it.</p>'
            f'<div class="workflow-actions">{buttons}</div>'
            f'<div class="status" id="{escape(status_id)}"></div>'
            "</div>"
        )

    state = signal.workflow_state
    buttons = []
    for candidate in SignalWorkflowState:
        tone = workflow_state_tone(candidate)
        active = " is-active" if candidate == state else ""
        buttons.append(
            f'<button class="workflow-button tone-{escape(tone)}{active}" '
            f'type="button" data-workflow-state="{escape(candidate.value)}" data-signal-id="{escape(signal.signal_id)}">'
            f"{escape(workflow_state_label(candidate))}"
            "</button>"
        )
    return (
        '<div class="workflow-panel">'
        '<div class="workflow-meta">'
        f'<div><span>Workflow</span><strong>{escape(workflow_state_label(state))}</strong></div>'
        f"{render_workflow_chip(signal)}"
        "</div>"
        f'<p class="workflow-summary">{escape(workflow_state_hint(state))}</p>'
        f'<div class="workflow-actions">{"".join(buttons)}</div>'
        f'<div class="status" id="{escape(status_id)}"></div>'
        "</div>"
    )
