from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.notifications.contracts import (
    TelegramOpsAlertItem,
    TelegramOpsAlertPreview,
    TelegramOpsAlertSendRequest,
    TelegramOpsAlertSendResult,
)
from libs.notifications.readiness import telegram_delivery_enabled
from libs.notifications.telegram import TelegramBotClient
from libs.observability.service import ObservabilityService
from libs.scheduler.service import SchedulerService
from libs.utils.config import settings


class TelegramOpsAlertService:
    def __init__(
        self,
        scheduler_service: SchedulerService,
        observability_service: ObservabilityService,
        client: TelegramBotClient | None = None,
    ) -> None:
        self.scheduler_service = scheduler_service
        self.observability_service = observability_service
        self.client = client or TelegramBotClient()

    def preview(
        self,
        *,
        stale_after_minutes: int | None = None,
        failed_runs_limit: int | None = None,
    ) -> TelegramOpsAlertPreview:
        generated_at = datetime.now(UTC)
        configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        stale_window = max(1, int(stale_after_minutes or settings.scheduler_alert_stale_after_minutes))
        failed_limit = min(max(int(failed_runs_limit or settings.scheduler_alert_failed_runs_limit), 1), 20)

        leader = self.scheduler_service.leader_status(as_of=generated_at)
        history = self.scheduler_service.list_run_history(limit=max(failed_limit, 10))
        latest_run = history[0] if history else None
        admin_health = self.observability_service.admin_health()

        alert_items: list[TelegramOpsAlertItem] = []
        if latest_run is not None:
            failed_runs = [item for item in history if item.status == "failed"][:failed_limit]
        else:
            failed_runs = []

        if failed_runs:
            first = failed_runs[0]
            alert_items.append(
                TelegramOpsAlertItem(
                    kind="scheduler_failed_runs",
                    severity="critical",
                    title=f"{len(failed_runs)} failed scheduler runs",
                    detail=f"Latest failure: {first.job_id} at {first.started_at.isoformat()}",
                )
            )

        stale_threshold = generated_at - timedelta(minutes=stale_window)
        latest_activity = latest_run.finished_at if latest_run is not None and latest_run.finished_at is not None else (
            latest_run.started_at if latest_run is not None else None
        )
        if not leader.owner_id:
            if latest_activity is None or latest_activity < stale_threshold:
                alert_items.append(
                    TelegramOpsAlertItem(
                        kind="scheduler_stale",
                        severity="warning",
                        title="Scheduler leader is stale",
                        detail=(
                            "No active leader lease and no recent scheduler activity "
                            f"within the last {stale_window} minutes."
                        ),
                    )
                )

        if admin_health.status != "ok":
            alert_items.append(
                TelegramOpsAlertItem(
                    kind="platform_health",
                    severity="warning" if admin_health.status == "degraded" else "critical",
                    title=f"Platform health is {admin_health.status}",
                    detail="Admin health reports degraded or not_ok operational state.",
                )
            )

        message = self._render_message(
            alert_items=alert_items,
            generated_at=generated_at,
            stale_after_minutes=stale_window,
            leader_owner=leader.owner_id,
        )
        return TelegramOpsAlertPreview(
            enabled=bool(settings.telegram_enabled),
            configured=configured,
            chat_id=settings.telegram_chat_id,
            parse_mode=settings.telegram_parse_mode,
            alert_items=alert_items,
            message=message,
            generated_at=generated_at,
        )

    def send(self, payload: TelegramOpsAlertSendRequest) -> TelegramOpsAlertSendResult:
        preview = self.preview(
            stale_after_minutes=payload.stale_after_minutes,
            failed_runs_limit=payload.failed_runs_limit,
        )
        if payload.dry_run:
            return TelegramOpsAlertSendResult(
                delivered=False,
                delivery_status="dry_run",
                chat_id=preview.chat_id,
                generated_at=preview.generated_at,
                preview=preview,
                detail="Telegram ops alert delivery skipped because dry_run=true.",
            )
        if not telegram_delivery_enabled():
            return TelegramOpsAlertSendResult(
                delivered=False,
                delivery_status="disabled",
                chat_id=preview.chat_id,
                generated_at=preview.generated_at,
                preview=preview,
                detail="Telegram delivery is disabled in settings.",
            )
        if not preview.configured:
            return TelegramOpsAlertSendResult(
                delivered=False,
                delivery_status="not_configured",
                chat_id=preview.chat_id,
                generated_at=preview.generated_at,
                preview=preview,
                detail="Telegram bot token or chat id is missing.",
            )

        response = self.client.send_message(
            token=str(settings.telegram_bot_token),
            chat_id=str(settings.telegram_chat_id),
            text=preview.message,
            parse_mode=settings.telegram_parse_mode,
            disable_web_page_preview=settings.telegram_disable_link_preview,
        )
        result_message = response.get("result", {}) if isinstance(response, dict) else {}
        return TelegramOpsAlertSendResult(
            delivered=True,
            delivery_status="sent",
            chat_id=preview.chat_id,
            generated_at=preview.generated_at,
            preview=preview,
            provider_message_id=str(result_message.get("message_id")) if result_message.get("message_id") is not None else None,
            detail="Telegram ops alert delivered.",
        )

    def _render_message(
        self,
        *,
        alert_items: list[TelegramOpsAlertItem],
        generated_at: datetime,
        stale_after_minutes: int,
        leader_owner: str | None,
    ) -> str:
        lines = [
            "<b>IMOEX Ops Alerts</b>",
            f"Generated: <b>{generated_at.isoformat()}</b>",
            f"Leader owner: <b>{leader_owner or 'none'}</b>",
            f"Stale window: <b>{stale_after_minutes}m</b>",
            "",
        ]
        if not alert_items:
            lines.append("No active ops alerts right now.")
        else:
            for index, item in enumerate(alert_items, start=1):
                lines.extend(
                    [
                        f"{index}. <b>{item.title}</b> [{item.severity}]",
                        f"   {item.detail}",
                    ]
                )
        return "\n".join(lines)
