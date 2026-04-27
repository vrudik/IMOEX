from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request, status

from libs.utils.config import settings


def admin_security_state() -> dict[str, Any]:
    environment = _current_environment()
    protected_environment = environment in _required_environments()
    configured = _admin_api_key_configured()
    return {
        "environment": environment,
        "protected_environment": protected_environment,
        "configured": configured,
        "required": configured or protected_environment,
        "header": _admin_api_key_header(),
    }


async def require_admin_api_key(request: Request) -> None:
    state = admin_security_state()
    if not state["required"]:
        return

    expected = (settings.admin_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is required for this environment but ADMIN_API_KEY is not configured.",
        )

    actual = request.headers.get(str(state["header"]))
    if actual is None or not secrets.compare_digest(actual, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key is missing or invalid.",
        )


def _current_environment() -> str:
    return (settings.app_environment or "local").strip().lower() or "local"


def _admin_api_key_configured() -> bool:
    return bool((settings.admin_api_key or "").strip())


def _admin_api_key_header() -> str:
    return (settings.admin_api_key_header or "X-IMOEX-Admin-Key").strip() or "X-IMOEX-Admin-Key"


def _required_environments() -> set[str]:
    raw = settings.admin_api_key_required_environments or ""
    return {item.strip().lower() for item in raw.split(",") if item.strip()}
