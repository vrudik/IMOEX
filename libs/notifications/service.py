from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from libs.dashboard.service import DashboardService
from libs.domain.contracts import JournalEntryKind, SignalStatus
from libs.notifications.contracts import (
    TelegramDeliveryEventKind,
    TelegramNotificationPreview,
    TelegramNotificationSendRequest,
    TelegramNotificationSendResult,
    TelegramDeliverySourceKind,
)
from libs.notifications.readiness import telegram_delivery_enabled, telegram_source_health
from libs.notifications.telegram import TelegramBotClient
from libs.preferences.contracts import NotificationEventKind
from libs.preferences.contracts import NotificationDeliveryActivityAction
from libs.preferences.service import NotificationPreferenceService
from libs.utils.config import settings


class TelegramNotificationService:
    def __init__(
        self,
        dashboard_service: DashboardService,
        preferences_service: NotificationPreferenceService | None = None,
        client: TelegramBotClient | None = None,
    ) -> None:
        self.dashboard_service = dashboard_service
        self.preferences_service = preferences_service
        self.client = client or TelegramBotClient()

    def preview(
        self,
        *,
        root: str | None = None,
        limit: int = 3,
        event_kind: TelegramDeliveryEventKind = TelegramDeliveryEventKind.DIGEST,
        delivery_source: TelegramDeliverySourceKind = TelegramDeliverySourceKind.MANUAL,
        ignore_quiet_hours: bool = False,
    ) -> TelegramNotificationPreview:
        selected_root = root
        if selected_root is None and self.preferences_service is not None:
            selected_root = self.preferences_service.resolve_default_root()

        snapshot = self.dashboard_service.build_snapshot(root=selected_root)
        selected_root = snapshot.selected_root
        effective_limit = max(1, int(limit))
        if self.preferences_service is not None:
            effective_limit = min(effective_limit, self.preferences_service.resolve_digest_limit())
        signals = self._select_signals(
            snapshot=snapshot,
            root=selected_root,
            event_kind=event_kind,
            limit=effective_limit,
        )
        configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        generated_at = datetime.now(UTC)
        quiet_hours_active = self.preferences_service.is_quiet_hours(at=generated_at) if self.preferences_service is not None else False
        event_allowed = (
            self.preferences_service.allows_event_kind(NotificationEventKind(event_kind.value))
            if self.preferences_service is not None
            else True
        )
        suppressed_reason = self._suppressed_reason(
            enabled=bool(settings.telegram_enabled),
            configured=configured,
            event_allowed=event_allowed,
            event_kind=event_kind,
            delivery_source=delivery_source,
            quiet_hours_active=quiet_hours_active,
            ignore_quiet_hours=ignore_quiet_hours,
            signals=signals,
        )
        message = self._render_message(
            snapshot=snapshot,
            signals=signals,
            event_kind=event_kind,
            suppressed_reason=suppressed_reason,
        )
        return TelegramNotificationPreview(
            root=selected_root,
            enabled=bool(settings.telegram_enabled),
            configured=configured,
            event_kind=event_kind,
            quiet_hours_active=quiet_hours_active,
            suppressed_reason=suppressed_reason,
            delivery_allowed=suppressed_reason is None,
            chat_id=settings.telegram_chat_id,
            parse_mode=settings.telegram_parse_mode,
            signal_ids=[item.signal_id for item in signals],
            message=message,
            generated_at=generated_at,
        )

    def send(self, payload: TelegramNotificationSendRequest) -> TelegramNotificationSendResult:
        preview = self.preview(
            root=payload.root,
            limit=payload.limit,
            event_kind=payload.event_kind,
            delivery_source=payload.delivery_source,
            ignore_quiet_hours=payload.ignore_quiet_hours,
        )
        result: TelegramNotificationSendResult
        if payload.dry_run:
            result = TelegramNotificationSendResult(
                delivered=False,
                delivery_status="dry_run",
                root=preview.root,
                chat_id=preview.chat_id,
                signal_ids=preview.signal_ids,
                generated_at=preview.generated_at,
                preview=preview,
                detail="Telegram delivery skipped because dry_run=true.",
            )
            self._record_delivery_activity(payload=payload, result=result)
            return result
        if not telegram_delivery_enabled():
            result = TelegramNotificationSendResult(
                delivered=False,
                delivery_status="disabled",
                root=preview.root,
                chat_id=preview.chat_id,
                signal_ids=preview.signal_ids,
                generated_at=preview.generated_at,
                preview=preview,
                detail="Telegram delivery is disabled in settings.",
            )
            self._record_delivery_activity(payload=payload, result=result)
            return result
        if not preview.configured:
            result = TelegramNotificationSendResult(
                delivered=False,
                delivery_status="not_configured",
                root=preview.root,
                chat_id=preview.chat_id,
                signal_ids=preview.signal_ids,
                generated_at=preview.generated_at,
                preview=preview,
                detail="Telegram bot token or chat id is missing.",
            )
            self._record_delivery_activity(payload=payload, result=result)
            return result
        if not preview.delivery_allowed:
            if (
                preview.suppressed_reason == "skip_next"
                and payload.delivery_source == TelegramDeliverySourceKind.SCHEDULE
                and self.preferences_service is not None
            ):
                self.preferences_service.clear_skip_next_event(NotificationEventKind(payload.event_kind.value))
            result = TelegramNotificationSendResult(
                delivered=False,
                delivery_status=preview.suppressed_reason or "suppressed",
                root=preview.root,
                chat_id=preview.chat_id,
                signal_ids=preview.signal_ids,
                generated_at=preview.generated_at,
                preview=preview,
                detail=self._suppression_detail(preview.suppressed_reason),
            )
            self._record_delivery_activity(payload=payload, result=result)
            return result

        response = self.client.send_message(
            token=str(settings.telegram_bot_token),
            chat_id=str(settings.telegram_chat_id),
            text=preview.message,
            parse_mode=settings.telegram_parse_mode,
            disable_web_page_preview=settings.telegram_disable_link_preview,
        )
        result_message = response.get("result", {}) if isinstance(response, dict) else {}
        result = TelegramNotificationSendResult(
            delivered=True,
            delivery_status="sent",
            root=preview.root,
            chat_id=preview.chat_id,
            signal_ids=preview.signal_ids,
            generated_at=preview.generated_at,
            preview=preview,
            provider_message_id=str(result_message.get("message_id")) if result_message.get("message_id") is not None else None,
            detail="Telegram message delivered.",
        )
        self._record_delivery_activity(payload=payload, result=result)
        return result

    def source_health(self):
        return telegram_source_health()

    def _select_signals(
        self,
        *,
        snapshot,
        root: str,
        event_kind: TelegramDeliveryEventKind,
        limit: int,
    ):
        if event_kind in {TelegramDeliveryEventKind.DIGEST, TelegramDeliveryEventKind.SIGNAL_OPEN}:
            signals = snapshot.spotlight_signals[:limit] or snapshot.recent_signals[:limit]
        elif event_kind == TelegramDeliveryEventKind.RESOLUTION:
            signals = self.dashboard_service.signal_service.list_signals(
                root=root,
                status=SignalStatus.RESOLVED,
                limit=max(limit * 2, 10),
            )
        else:
            resolved = self.dashboard_service.signal_service.list_signals(
                root=root,
                status=SignalStatus.RESOLVED,
                limit=max(limit * 3, 12),
            )
            signals = []
            for item in resolved:
                detail = self.dashboard_service.signal_service.get_signal(item.signal_id)
                if detail is None:
                    continue
                if any(entry.kind == JournalEntryKind.POST_MORTEM for entry in detail.journal_entries):
                    signals.append(detail)
                if len(signals) >= limit:
                    break
        if self.preferences_service is not None:
            return self.preferences_service.filter_signal_cards(signals)[:limit]
        return signals[:limit]

    def _suppressed_reason(
        self,
        *,
        enabled: bool,
        configured: bool,
        event_allowed: bool,
        event_kind: TelegramDeliveryEventKind,
        delivery_source: TelegramDeliverySourceKind,
        quiet_hours_active: bool,
        ignore_quiet_hours: bool,
        signals,
    ) -> str | None:
        if not enabled:
            return "disabled"
        if not configured:
            return "not_configured"
        if not event_allowed:
            return "event_disabled"
        if (
            delivery_source == TelegramDeliverySourceKind.SCHEDULE
            and self.preferences_service is not None
            and self.preferences_service.should_skip_next_event(NotificationEventKind(event_kind.value))
        ):
            return "skip_next"
        if (
            quiet_hours_active
            and not ignore_quiet_hours
            and self.preferences_service is not None
            and self.preferences_service.should_suppress_during_quiet_hours()
        ):
            return "quiet_hours"
        if not signals:
            return "no_candidates"
        return None

    def _suppression_detail(self, suppressed_reason: str | None) -> str:
        if suppressed_reason == "quiet_hours":
            return "Telegram delivery suppressed because quiet hours are active."
        if suppressed_reason == "skip_next":
            return "Telegram delivery skipped because the next run was muted by the user."
        if suppressed_reason == "event_disabled":
            return "Telegram delivery suppressed because this event type is disabled in preferences."
        if suppressed_reason == "no_candidates":
            return "Telegram delivery skipped because no matching signals were found."
        if suppressed_reason == "disabled":
            return "Telegram delivery is disabled in settings."
        if suppressed_reason == "not_configured":
            return "Telegram bot token or chat id is missing."
        return "Telegram delivery was suppressed."

    def _render_message(
        self,
        *,
        snapshot,
        signals,
        event_kind: TelegramDeliveryEventKind,
        suppressed_reason: str | None,
    ) -> str:
        lines = [
            f"<b>IMOEX Signal Brief · {snapshot.selected_root}</b>",
            f"Session: <b>{snapshot.root_details.session.session_type.value if snapshot.root_details else 'unknown'}</b>",
            f"Platform: <b>{snapshot.admin_health.status}</b>",
            f"Resolved: <b>{snapshot.evaluation.resolved_signals}</b>",
            "",
        ]
        if not signals:
            lines.append("No signals available right now.")
        else:
            for index, signal in enumerate(signals, start=1):
                lines.extend(
                    [
                        f"{index}. <b>{signal.root} {signal.contract}</b> · {signal.direction_final.value} · {signal.horizon.value}",
                        f"   confidence {signal.confidence_final:.2f} · skeptic {signal.skeptic_score:.2f} · priority {signal.priority_score}",
                        f"   {signal.summary}",
                    ]
                )
        if snapshot.root_details is not None:
            lines.extend(
                [
                    "",
                    f"Roll share: <b>{snapshot.root_details.continuous_series.next_contract_share:.0%}</b>",
            f"Rule set: <b>{snapshot.root_details.session.effective_rule_set}</b>",
                ]
            )
        return "\n".join(lines)

    def _record_delivery_activity(
        self,
        *,
        payload: TelegramNotificationSendRequest,
        result: TelegramNotificationSendResult,
    ) -> None:
        action = NotificationDeliveryActivityAction.SCHEDULE_DELIVERY
        if payload.delivery_source == TelegramDeliverySourceKind.MANUAL:
            action = (
                NotificationDeliveryActivityAction.SEND_NOW_FORCE
                if payload.ignore_quiet_hours
                else NotificationDeliveryActivityAction.SEND_NOW
            )
        self.dashboard_service.repository.add_notification_delivery_event(
            activity_id=f"delivery-activity-{uuid4().hex}",
            profile_id="default",
            action=action.value,
            event_kind=payload.event_kind.value,
            delivery_source=payload.delivery_source.value,
            root_code=result.root,
            status=result.delivery_status,
            detail=result.detail or result.preview.suppressed_reason or "Delivery action completed.",
            signal_ids_json=json.dumps(result.signal_ids, ensure_ascii=False),
            provider_message_id=result.provider_message_id,
            created_at=result.generated_at,
        )
