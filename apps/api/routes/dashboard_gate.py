from __future__ import annotations

from fastapi import HTTPException

from libs.runtime.feature_flags import is_feature_enabled

DASHBOARD_FEATURE_FLAG = "dashboard_ui"
DASHBOARD_DISABLED_DETAIL = "Dashboard feature is disabled."


def ensure_dashboard_enabled() -> None:
    if not is_feature_enabled(DASHBOARD_FEATURE_FLAG):
        raise HTTPException(status_code=404, detail=DASHBOARD_DISABLED_DETAIL)
