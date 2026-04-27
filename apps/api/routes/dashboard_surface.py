from __future__ import annotations

from html import escape


def surface_state_palette(tone: str) -> tuple[str, str, str]:
    if tone == "positive":
        return ("rgba(47, 126, 87, 0.14)", "rgba(47, 126, 87, 0.28)", "#2f7e57")
    if tone == "negative":
        return ("rgba(180, 74, 61, 0.14)", "rgba(180, 74, 61, 0.28)", "#b44a3d")
    if tone == "warning":
        return ("rgba(186, 112, 33, 0.14)", "rgba(186, 112, 33, 0.28)", "#ba7021")
    return ("rgba(23, 56, 79, 0.08)", "rgba(23, 56, 79, 0.12)", "#17384f")


def render_surface_state_strip(
    *,
    strip_key: str,
    title: str,
    note: str,
    items: list[dict[str, str]],
) -> str:
    if not items:
        return ""
    cards = []
    for item in items:
        tone = item.get("tone", "neutral")
        background, border, ink = surface_state_palette(tone)
        cards.append(
            "<article data-surface-state-card "
            f'data-state-tone="{escape(tone)}" '
            f'style="padding:16px 18px;border-radius:20px;border:1px solid {border};background:{background};display:grid;gap:8px;align-content:start;">'
            '<div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">'
            f'<strong style="font-size:15px;line-height:1.35;">{escape(item.get("label", "State"))}</strong>'
            f'<span style="display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,0.74);color:{ink};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">{escape(item.get("status", tone))}</span>'
            "</div>"
            f'<p class="muted" style="margin:0;line-height:1.55;">{escape(item.get("detail", ""))}</p>'
            "</article>"
        )
    return (
        f'<section class="panel" data-surface-state-strip="{escape(strip_key)}">'
        '<div class="panel-head">'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(note)}</p>"
        "</div>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;">'
        f'{"".join(cards)}'
        "</div>"
        "</section>"
    )
