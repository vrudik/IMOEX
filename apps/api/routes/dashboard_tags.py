from __future__ import annotations

from html import escape


def render_tag_chips(tags, *, empty: str = "") -> str:
    chips = "".join(f'<span class="filter-chip">{escape(str(tag))}</span>' for tag in tags if str(tag).strip())
    if chips:
        return f'<div class="tag-chip-row" data-journal-tags>{chips}</div>'
    if not empty:
        return ""
    return f'<div class="tag-chip-row" data-journal-tags><span class="filter-chip">{escape(empty)}</span></div>'


def render_tag_picker(tags, *, disabled: bool = False) -> str:
    disabled_attr = " disabled" if disabled else ""
    options = "".join(
        '<label class="tag-option">'
        f'<input type="checkbox" name="tags" value="{escape(str(tag))}"{disabled_attr}>'
        f"<span>{escape(str(tag))}</span>"
        "</label>"
        for tag in tags
        if str(tag).strip()
    )
    if not options:
        return ""
    return (
        '<div class="tag-picker" data-journal-tag-picker>'
        '<span class="muted">Review tags</span>'
        f'<div class="tag-picker-options">{options}</div>'
        "</div>"
    )
