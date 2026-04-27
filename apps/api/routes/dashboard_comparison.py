from __future__ import annotations

from html import escape


def render_horizon_comparison(snapshot) -> str:
    if snapshot is None:
        return (
            '<section class="panel">'
            '<div class="panel-head"><h2>Horizon compare</h2><p>No horizon comparison is available yet.</p></div>'
            "</section>"
        )
    rows = "".join(
        (
            "<article>"
            f"<strong>{escape(item.horizon)} | {escape(item.direction)}</strong>"
            f'<p class="muted">confidence {item.confidence:.2f} | skeptic {item.skeptic_score:.2f} | attention {item.attention_score:.2f}</p>'
            f'<p class="muted">{escape(item.summary)}</p>'
            "</article>"
        )
        for item in snapshot.items
    )
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Horizon compare</h2><p>Read the root across multiple horizons in one place.</p></div>'
        f'<div class="metric-list">{rows}</div>'
        "</section>"
    )


def render_signal_diff(diff) -> str:
    if diff is None:
        return ""
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>What changed since last cycle?</h2><p>Diff vs the previous recalculation.</p></div>'
        '<div class="metric-list">'
        f'<article><strong>{escape(diff.summary)}</strong><p class="muted">Prob up {diff.probability_up_delta:+.2f} | confidence {diff.confidence_delta:+.2f} | skeptic {diff.skeptic_delta:+.2f} | freshness {diff.freshness_delta:+.2f}</p></article>'
        f'<article><strong>Drivers</strong><p class="muted">Added: {escape(", ".join(diff.drivers_added) or "none")} | Removed: {escape(", ".join(diff.drivers_removed) or "none")}</p></article>'
        f'<article><strong>Invalidation</strong><p class="muted">Added: {escape(", ".join(diff.invalidations_added) or "none")} | Removed: {escape(", ".join(diff.invalidations_removed) or "none")}</p></article>'
        "</div>"
        "</section>"
    )
