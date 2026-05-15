from __future__ import annotations

import json

from apps.api.routes.dashboard_delivery import delivery_activity_reason
from libs.preferences.contracts import NotificationDeliveryActivityExportFormat


def render_delivery_activity_export(items, export_format: NotificationDeliveryActivityExportFormat) -> tuple[str, str]:
    if export_format == NotificationDeliveryActivityExportFormat.JSONL:
        body = "\n".join(json.dumps(_delivery_activity_export_payload(item), ensure_ascii=False) for item in items)
        return body, "application/x-ndjson"

    lines = [
        "activity_id,action,event_kind,delivery_source,root_scope,status,detail,signal_count,provider_message_id,created_at,reason_label"
    ]
    for item in items:
        cells = [
            item.activity_id,
            item.action.value,
            item.event_kind.value,
            item.delivery_source or "",
            item.root_scope or "",
            item.status,
            item.detail.replace('"', "'"),
            str(len(item.signal_ids)),
            item.provider_message_id or "",
            item.created_at.isoformat(),
            delivery_activity_reason(item.status).replace('"', "'"),
        ]
        lines.append(",".join(f'"{cell}"' for cell in cells))
    return "\n".join(lines), "text/csv"


def _delivery_activity_export_payload(item) -> dict:
    payload = item.model_dump(mode="json")
    payload["reason_label"] = delivery_activity_reason(item.status)
    return payload
