from __future__ import annotations

import json
from datetime import UTC, datetime, time
from uuid import uuid4

from libs.domain.contracts import HorizonCode, RootSeriesSummary
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.preferences.contracts import (
    NotificationDeliveryActivityAction,
    NotificationEventKind,
    NotificationPreferenceSnapshot,
    NotificationPreferenceUpdate,
    NotificationPreferenceWorkspaceSnapshot,
)
from libs.utils.config import settings


class NotificationPreferenceService:
    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        *,
        list_roots_callable,
    ) -> None:
        self.repository = repository
        self.list_roots_callable = list_roots_callable

    def get_preferences(self, profile_id: str = "default") -> NotificationPreferenceSnapshot:
        row = self.repository.get_user_notification_preferences(profile_id=profile_id)
        roots = self._available_roots()
        available_root_codes = {item.root_code for item in roots}
        available_horizons = list(HorizonCode)
        available_event_kinds = list(NotificationEventKind)

        if row is None:
            default_root = roots[0].root_code if roots else None
            subscribed_roots = [default_root] if default_root is not None else []
            subscribed_horizons = available_horizons
            return NotificationPreferenceSnapshot(
                profile_id=profile_id,
                default_root=default_root,
                subscribed_roots=subscribed_roots,
                subscribed_horizons=subscribed_horizons,
                subscribed_event_kinds=available_event_kinds,
                skip_next_event_kinds=[],
                min_priority_score=0,
                quiet_hours_start=None,
                quiet_hours_end=None,
                suppress_during_quiet_hours=True,
                digest_limit=3,
                updated_at=None,
            )

        subscribed_roots = [
            item for item in self._decode_string_list(row.subscribed_roots_json) if item in available_root_codes
        ]
        subscribed_horizons = [
            horizon
            for horizon in self._decode_horizon_list(row.subscribed_horizons_json)
            if horizon in available_horizons
        ]
        subscribed_event_kinds = [
            item
            for item in self._decode_event_kind_list(row.subscribed_event_kinds_json)
            if item in available_event_kinds
        ]
        skip_next_event_kinds = [
            item
            for item in self._decode_event_kind_list(row.skip_next_event_kinds_json)
            if item in available_event_kinds
        ]
        default_root = row.default_root if row.default_root in available_root_codes else (roots[0].root_code if roots else None)
        if default_root is not None and default_root not in subscribed_roots:
            subscribed_roots = [default_root, *subscribed_roots]
        if not subscribed_horizons:
            subscribed_horizons = available_horizons
        if not subscribed_event_kinds:
            subscribed_event_kinds = available_event_kinds

        return NotificationPreferenceSnapshot(
            profile_id=row.profile_id,
            default_root=default_root,
            subscribed_roots=subscribed_roots,
            subscribed_horizons=subscribed_horizons,
            subscribed_event_kinds=subscribed_event_kinds,
            skip_next_event_kinds=skip_next_event_kinds,
            min_priority_score=int(row.min_priority_score),
            quiet_hours_start=row.quiet_hours_start,
            quiet_hours_end=row.quiet_hours_end,
            suppress_during_quiet_hours=bool(row.suppress_during_quiet_hours),
            digest_limit=int(row.digest_limit),
            updated_at=row.updated_at,
        )

    def update_preferences(
        self,
        payload: NotificationPreferenceUpdate,
        *,
        profile_id: str = "default",
    ) -> NotificationPreferenceSnapshot:
        roots = self._available_roots()
        available_root_codes = {item.root_code for item in roots}
        available_horizons = list(HorizonCode)
        available_event_kinds = list(NotificationEventKind)

        default_root = payload.default_root if payload.default_root in available_root_codes else None
        subscribed_roots = [item for item in payload.subscribed_roots if item in available_root_codes]
        if default_root is not None and default_root not in subscribed_roots:
            subscribed_roots.insert(0, default_root)
        if not subscribed_roots and default_root is None and roots:
            default_root = roots[0].root_code
            subscribed_roots = [default_root]

        subscribed_horizons = [item for item in payload.subscribed_horizons if item in available_horizons]
        if not subscribed_horizons:
            subscribed_horizons = available_horizons
        subscribed_event_kinds = [item for item in payload.subscribed_event_kinds if item in available_event_kinds]
        if not subscribed_event_kinds:
            subscribed_event_kinds = available_event_kinds

        quiet_hours_start = self._normalize_hhmm(payload.quiet_hours_start)
        quiet_hours_end = self._normalize_hhmm(payload.quiet_hours_end)
        updated_at = datetime.now(UTC)
        existing_row = self.repository.get_user_notification_preferences(profile_id=profile_id)
        self.repository.upsert_user_notification_preferences(
            profile_id=profile_id,
            default_root=default_root,
            subscribed_roots_json=json.dumps(subscribed_roots, ensure_ascii=False),
            subscribed_horizons_json=json.dumps([item.value for item in subscribed_horizons], ensure_ascii=False),
            subscribed_event_kinds_json=json.dumps(
                [item.value for item in subscribed_event_kinds],
                ensure_ascii=False,
            ),
            skip_next_event_kinds_json=(
                existing_row.skip_next_event_kinds_json if existing_row is not None else "[]"
            ),
            min_priority_score=int(payload.min_priority_score),
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            suppress_during_quiet_hours=bool(payload.suppress_during_quiet_hours),
            digest_limit=int(payload.digest_limit),
            updated_at=updated_at,
        )
        return self.get_preferences(profile_id=profile_id)

    def build_workspace_snapshot(self) -> NotificationPreferenceWorkspaceSnapshot:
        preferences = self.get_preferences()
        return NotificationPreferenceWorkspaceSnapshot(
            generated_at=datetime.now(UTC),
            roots=self._available_roots(),
            available_horizons=list(HorizonCode),
            preferences=preferences,
            telegram_configured=bool(settings.telegram_bot_token and settings.telegram_chat_id),
            telegram_enabled=bool(settings.telegram_enabled),
        )

    def resolve_default_root(self) -> str | None:
        return self.get_preferences().default_root

    def resolve_digest_limit(self) -> int:
        return self.get_preferences().digest_limit

    def allows_event_kind(self, event_kind: NotificationEventKind | str) -> bool:
        preferences = self.get_preferences()
        normalized = self._coerce_event_kind(event_kind)
        return normalized in preferences.subscribed_event_kinds

    def should_suppress_during_quiet_hours(self) -> bool:
        return self.get_preferences().suppress_during_quiet_hours

    def should_skip_next_event(self, event_kind: NotificationEventKind | str) -> bool:
        preferences = self.get_preferences()
        normalized = self._coerce_event_kind(event_kind)
        return normalized in preferences.skip_next_event_kinds

    def mark_skip_next_event(
        self,
        event_kind: NotificationEventKind | str,
        *,
        profile_id: str = "default",
    ) -> NotificationPreferenceSnapshot:
        preferences = self.get_preferences(profile_id=profile_id)
        normalized = self._coerce_event_kind(event_kind)
        event_kinds = list(preferences.skip_next_event_kinds)
        if normalized not in event_kinds:
            event_kinds.append(normalized)
        snapshot = self._persist_snapshot(
            preferences=preferences,
            profile_id=profile_id,
            skip_next_event_kinds=event_kinds,
        )
        self._record_delivery_activity(
            profile_id=profile_id,
            action=NotificationDeliveryActivityAction.SKIP_NEXT,
            event_kind=normalized,
            root_code=snapshot.default_root,
            status="updated",
            detail=f"Next {normalized.value} delivery will be skipped once.",
        )
        return snapshot

    def clear_skip_next_event(
        self,
        event_kind: NotificationEventKind | str,
        *,
        profile_id: str = "default",
    ) -> NotificationPreferenceSnapshot:
        preferences = self.get_preferences(profile_id=profile_id)
        normalized = self._coerce_event_kind(event_kind)
        snapshot = self._persist_snapshot(
            preferences=preferences,
            profile_id=profile_id,
            skip_next_event_kinds=[item for item in preferences.skip_next_event_kinds if item != normalized],
        )
        self._record_delivery_activity(
            profile_id=profile_id,
            action=NotificationDeliveryActivityAction.UNDO_SKIP,
            event_kind=normalized,
            root_code=snapshot.default_root,
            status="updated",
            detail=f"One-shot skip for {normalized.value} delivery was removed.",
        )
        return snapshot

    def filter_signal_cards(self, signals):
        preferences = self.get_preferences()
        allowed_roots = set(preferences.subscribed_roots)
        allowed_horizons = set(preferences.subscribed_horizons)
        return [
            signal
            for signal in signals
            if (not allowed_roots or signal.root in allowed_roots)
            and signal.horizon in allowed_horizons
            and signal.priority_score >= preferences.min_priority_score
        ]

    def is_quiet_hours(self, *, at: datetime | None = None) -> bool:
        preferences = self.get_preferences()
        if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
            return False
        now = (at or datetime.now(UTC)).time()
        start = self._parse_hhmm(preferences.quiet_hours_start)
        end = self._parse_hhmm(preferences.quiet_hours_end)
        if start is None or end is None:
            return False
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    def _available_roots(self) -> list[RootSeriesSummary]:
        return self.list_roots_callable()

    def _persist_snapshot(
        self,
        *,
        preferences: NotificationPreferenceSnapshot,
        profile_id: str,
        skip_next_event_kinds: list[NotificationEventKind] | None = None,
    ) -> NotificationPreferenceSnapshot:
        updated_at = datetime.now(UTC)
        self.repository.upsert_user_notification_preferences(
            profile_id=profile_id,
            default_root=preferences.default_root,
            subscribed_roots_json=json.dumps(preferences.subscribed_roots, ensure_ascii=False),
            subscribed_horizons_json=json.dumps(
                [item.value for item in preferences.subscribed_horizons],
                ensure_ascii=False,
            ),
            subscribed_event_kinds_json=json.dumps(
                [item.value for item in preferences.subscribed_event_kinds],
                ensure_ascii=False,
            ),
            skip_next_event_kinds_json=json.dumps(
                [
                    item.value
                    for item in (
                        skip_next_event_kinds
                        if skip_next_event_kinds is not None
                        else preferences.skip_next_event_kinds
                    )
                ],
                ensure_ascii=False,
            ),
            min_priority_score=int(preferences.min_priority_score),
            quiet_hours_start=preferences.quiet_hours_start,
            quiet_hours_end=preferences.quiet_hours_end,
            suppress_during_quiet_hours=bool(preferences.suppress_during_quiet_hours),
            digest_limit=int(preferences.digest_limit),
            updated_at=updated_at,
        )
        return self.get_preferences(profile_id=profile_id)

    def _record_delivery_activity(
        self,
        *,
        profile_id: str,
        action: NotificationDeliveryActivityAction,
        event_kind: NotificationEventKind,
        root_code: str | None,
        status: str,
        detail: str,
    ) -> None:
        self.repository.add_notification_delivery_event(
            activity_id=f"delivery-activity-{uuid4().hex}",
            profile_id=profile_id,
            action=action.value,
            event_kind=event_kind.value,
            delivery_source="manual",
            root_code=root_code,
            status=status,
            detail=detail,
            signal_ids_json="[]",
            provider_message_id=None,
            created_at=datetime.now(UTC),
        )

    def _decode_string_list(self, payload: str) -> list[str]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, list):
            return []
        return [str(item) for item in decoded]

    def _decode_horizon_list(self, payload: str) -> list[HorizonCode]:
        decoded = self._decode_string_list(payload)
        result: list[HorizonCode] = []
        for item in decoded:
            try:
                result.append(HorizonCode(item))
            except ValueError:
                continue
        return result

    def _decode_event_kind_list(self, payload: str) -> list[NotificationEventKind]:
        decoded = self._decode_string_list(payload)
        result: list[NotificationEventKind] = []
        for item in decoded:
            try:
                result.append(NotificationEventKind(item))
            except ValueError:
                continue
        return result

    def _coerce_event_kind(self, value: NotificationEventKind | str) -> NotificationEventKind:
        if isinstance(value, NotificationEventKind):
            return value
        return NotificationEventKind(str(value))

    def _normalize_hhmm(self, value: str | None) -> str | None:
        parsed = self._parse_hhmm(value)
        if parsed is None:
            return None
        return f"{parsed.hour:02d}:{parsed.minute:02d}"

    def _parse_hhmm(self, value: str | None) -> time | None:
        if value is None or not value.strip():
            return None
        parts = value.strip().split(":")
        if len(parts) != 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return time(hour=hour, minute=minute)
