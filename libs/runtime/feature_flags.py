from __future__ import annotations

from libs.runtime.contracts import FeatureFlagState
from libs.utils.config import settings

DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "dashboard_ui": True,
    "telegram_delivery": True,
    "runtime_metrics": True,
    "structured_logging": True,
}


def resolved_feature_flags() -> dict[str, bool]:
    flags = dict(DEFAULT_FEATURE_FLAGS)
    flags.update(settings.feature_flags)
    return flags


def is_feature_enabled(name: str) -> bool:
    return bool(resolved_feature_flags().get(name, False))


def list_feature_flags() -> list[FeatureFlagState]:
    return [
        FeatureFlagState(
            name=name,
            enabled=enabled,
            detail="enabled via default/runtime settings merge",
        )
        for name, enabled in sorted(resolved_feature_flags().items())
    ]
