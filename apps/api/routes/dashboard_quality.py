from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from apps.api.routes.dashboard_formatting import format_optional
from libs.domain.contracts import JournalEntryKind, SignalStatus


def journal_filter_href(
    *,
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
    tag: str | None = None,
) -> str:
    params: dict[str, str] = {}
    if root is not None:
        params["root"] = root
    if status is not None:
        params["status"] = status.value
    if kind is not None:
        params["kind"] = kind.value
    if tag is not None:
        params["tag"] = tag
    if not params:
        return "/workspace/journal"
    return f"/workspace/journal?{urlencode(params)}"


def render_quality_pair(pair) -> str:
    latest_contract = pair.latest_contract or "n/a"
    mismatch = format_optional(pair.mismatch_rate_overlap)
    return (
        "<article>"
        f"<strong>{escape(pair.provider_a)} vs {escape(pair.provider_b)}</strong>"
        f"<p>contracts {pair.contracts_count} \u00b7 latest {escape(latest_contract)} \u00b7 mismatch {escape(mismatch)}</p>"
        "</article>"
    )
