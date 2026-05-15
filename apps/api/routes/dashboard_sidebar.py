from __future__ import annotations

from html import escape
from urllib.parse import urlencode


def render_page_sidebar_styles(max_width: str) -> str:
    return f"""
    .page-shell {{
      width: min({max_width}, calc(100% - 28px));
      margin: 20px auto 36px;
      display: grid;
      grid-template-columns: 248px minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }}
    .shell {{
      width: 100%;
      margin: 0;
    }}
    .page-sidebar {{
      position: sticky;
      top: 18px;
      align-self: start;
    }}
    .sidebar-card {{
      background: var(--paper, var(--panel));
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 18px;
      display: grid;
      gap: 12px;
      backdrop-filter: blur(14px);
    }}
    .sidebar-kicker {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy, var(--teal));
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .sidebar-title {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .sidebar-nav {{
      display: grid;
      gap: 8px;
    }}
    .sidebar-link {{
      display: block;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      font-weight: 700;
    }}
    .sidebar-link.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    .sidebar-meta {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
    }}
    .sidebar-switch {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      display: grid;
      gap: 10px;
    }}
    .sidebar-switch select {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.84);
      color: var(--ink);
      font: inherit;
    }}
    .sidebar-meta label {{
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .sidebar-switch label {{
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .sidebar-meta strong {{
      font-size: 18px;
    }}
    .sidebar-meta small {{
      display: block;
      margin-top: 6px;
      color: var(--muted);
      line-height: 1.45;
    }}
    @media (max-width: 1040px) {{
      .page-shell {{
        grid-template-columns: 1fr;
        width: min(100% - 16px, {max_width});
      }}
      .page-sidebar {{
        position: static;
      }}
      .sidebar-nav {{
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      }}
    }}
"""


def render_page_sidebar(
    page_key: str,
    *,
    root: str | None = None,
    roots=None,
    signal_id: str | None = None,
) -> str:
    items = [
        ("workspace", "Workspace", _with_optional_root("/workspace", root=root)),
        ("dashboard", "Operations", _with_optional_root("/dashboard", root=root)),
        ("council", "Decision flow", _with_optional_root("/workspace/council", root=root)),
        ("runtime", "Runtime control", _with_optional_root("/workspace/runtime", root=root)),
        ("journal", "Journal", _with_optional_root("/workspace/journal", root=root)),
        ("preferences", "Preferences", _with_optional_root("/workspace/preferences", root=root)),
        ("delivery-history", "Delivery history", _with_optional_root("/workspace/delivery-history", root=root)),
    ]
    if signal_id:
        items.append(("signal", "Signal detail", f"/workspace/signals/{escape(signal_id)}"))

    links = "".join(
        f'<a class="sidebar-link{" is-active" if key == page_key else ""}" href="{href}" data-swap-link>{label}</a>'
        for key, label, href in items
    )
    selected_root = _sidebar_selected_root(roots or [], root)
    current_root = selected_root.root_code if selected_root is not None else (root or "auto")
    switch_markup = ""
    if roots:
        fallback_attr = ' data-fallback-path="/workspace"' if page_key == "signal" else ""
        options = "".join(
            (
                f'<option value="{escape(item.root_code)}"'
                f'{" selected" if item.root_code == current_root else ""}>'
                f"{escape(item.root_code)} &middot; {escape(item.active_contract)} &middot; {escape(item.base_asset)}"
                "</option>"
            )
            for item in roots
        )
        switch_markup = (
            '<div class="sidebar-switch">'
            '<label for="sidebar-root-switch">Switch instrument</label>'
            f'<select id="sidebar-root-switch" data-root-switch data-page-key="{escape(page_key)}"{fallback_attr}>'
            f"{options}"
            "</select>"
            "</div>"
        )
    meta_detail = ""
    if selected_root is not None:
        meta_detail = (
            f'<small>{escape(selected_root.active_contract)} &middot; {escape(selected_root.base_asset)}</small>'
        )
    return (
        '<aside class="page-sidebar">'
        '<div class="sidebar-card">'
        '<span class="sidebar-kicker">Navigation</span>'
        '<h2 class="sidebar-title">Move around the workspace</h2>'
        '<p class="muted">Jump between the main pages for the current root and signal.</p>'
        f'<div class="sidebar-nav">{links}</div>'
        f"{switch_markup}"
        f'<div class="sidebar-meta"><label>Current instrument</label><strong>{escape(current_root)}</strong>{meta_detail}</div>'
        "</div>"
        "</aside>"
    )


def _with_optional_root(path: str, *, root: str | None = None) -> str:
    if not root:
        return path
    return f"{path}?{urlencode({'root': root})}"


def _sidebar_selected_root(roots, root: str | None):
    if roots:
        if root:
            match = next((item for item in roots if item.root_code == root), None)
            if match is not None:
                return match
        return roots[0]
    return None
