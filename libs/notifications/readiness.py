from __future__ import annotations

from libs.domain.contracts import HealthStatus, SourceHealth
from libs.utils.config import settings


def telegram_delivery_enabled() -> bool:
    return bool(settings.telegram_enabled)


def telegram_delivery_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def telegram_source_health() -> SourceHealth:
    enabled = telegram_delivery_enabled()
    configured = telegram_delivery_configured()
    if enabled and configured:
        status = HealthStatus.OK
        detail = "telegram delivery channel is configured"
    elif enabled and not configured:
        status = HealthStatus.DEGRADED
        detail = "telegram enabled but bot token/chat id is incomplete"
    else:
        status = HealthStatus.DEGRADED
        detail = "telegram delivery channel is disabled"
    return SourceHealth(
        provider="telegram",
        role="delivery",
        status=status,
        detail=detail,
        freshness_seconds=None,
        primary=False,
    )
