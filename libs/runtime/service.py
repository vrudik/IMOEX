from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from libs.dashboard.contracts import (
    ModelRoleAssignment,
    RuntimeAuditEvent,
    RuntimeControlSnapshot,
    RuntimeFreshnessPolicySnapshot,
    RuntimeFreshnessPolicyUpdate,
    RuntimeModelRouteUpdate,
)
from libs.domain.repository import SqlAlchemyContractMasterRepository


class RuntimeControlService:
    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def get_snapshot(self) -> RuntimeControlSnapshot:
        generated_at = datetime.now(UTC)
        return RuntimeControlSnapshot(
            generated_at=generated_at,
            model_routes=self.list_model_routes(),
            freshness_policy=self.get_freshness_policy(),
            audit_trail=self.list_audit_trail(limit=25),
        )

    def list_model_routes(self) -> list[ModelRoleAssignment]:
        rows = self.repository.list_runtime_model_routes()
        if not rows:
            return self._default_model_routes()
        return [
            ModelRoleAssignment(
                role_key=row.role_key,
                role_label=self._role_label(row.role_key),
                owner=row.owner,
                product=row.product,
                model=row.model,
                control_mode=row.control_mode,
                detail=row.detail,
            )
            for row in rows
        ]

    def update_model_route(self, payload: RuntimeModelRouteUpdate) -> RuntimeControlSnapshot:
        updated_at = datetime.now(UTC)
        self.repository.upsert_runtime_model_route(
            role_key=payload.role_key,
            owner=payload.owner,
            product=payload.product,
            model=payload.model,
            control_mode=payload.control_mode,
            detail=payload.detail,
            updated_at=updated_at,
        )
        self._record_audit(
            category="model_route",
            action="update",
            target_key=payload.role_key,
            detail=f"Updated runtime routing for {payload.role_key}.",
            payload=payload.model_dump(mode="json"),
        )
        return self.get_snapshot()

    def reset_model_routes(self) -> RuntimeControlSnapshot:
        self.repository.delete_runtime_model_routes()
        for item in self._default_model_routes():
            self.repository.upsert_runtime_model_route(
                role_key=item.role_key,
                owner=item.owner,
                product=item.product,
                model=item.model,
                control_mode=item.control_mode,
                detail=item.detail,
                updated_at=datetime.now(UTC),
            )
        self._record_audit(
            category="model_route",
            action="reset",
            target_key=None,
            detail="Reset runtime model routes to defaults.",
            payload={"roles": [item.role_key for item in self._default_model_routes()]},
        )
        return self.get_snapshot()

    def get_freshness_policy(self) -> RuntimeFreshnessPolicySnapshot:
        row = self.repository.get_runtime_freshness_policy()
        if row is None:
            return RuntimeFreshnessPolicySnapshot()
        return RuntimeFreshnessPolicySnapshot(
            fresh_max_seconds=row.fresh_max_seconds,
            aging_max_seconds=row.aging_max_seconds,
            stale_max_seconds=row.stale_max_seconds,
            degraded_max_seconds=row.degraded_max_seconds,
        )

    def update_freshness_policy(self, payload: RuntimeFreshnessPolicyUpdate) -> RuntimeControlSnapshot:
        updated_at = datetime.now(UTC)
        self.repository.upsert_runtime_freshness_policy(
            policy_key="default",
            fresh_max_seconds=payload.fresh_max_seconds,
            aging_max_seconds=payload.aging_max_seconds,
            stale_max_seconds=payload.stale_max_seconds,
            degraded_max_seconds=payload.degraded_max_seconds,
            updated_at=updated_at,
        )
        self._record_audit(
            category="freshness_policy",
            action="update",
            target_key="default",
            detail="Updated freshness SLA thresholds.",
            payload=payload.model_dump(mode="json"),
        )
        return self.get_snapshot()

    def list_audit_trail(self, *, limit: int = 25) -> list[RuntimeAuditEvent]:
        rows = self.repository.list_runtime_audit_events(limit=limit)
        events: list[RuntimeAuditEvent] = []
        for row in rows:
            try:
                payload = json.loads(row.payload_json)
            except json.JSONDecodeError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            events.append(
                RuntimeAuditEvent(
                    event_id=row.event_id,
                    category=row.category,
                    action=row.action,
                    target_key=row.target_key,
                    detail=row.detail,
                    payload=payload,
                    created_at=row.created_at,
                )
            )
        return events

    def _record_audit(
        self,
        *,
        category: str,
        action: str,
        target_key: str | None,
        detail: str,
        payload: dict[str, object],
    ) -> None:
        self.repository.add_runtime_audit_event(
            event_id=f"runtime-audit-{uuid4().hex}",
            category=category,
            action=action,
            target_key=target_key,
            detail=detail,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            created_at=datetime.now(UTC),
        )

    def _default_model_routes(self) -> list[ModelRoleAssignment]:
        detail = "Editable runtime mapping for the trader council."
        return [
            ModelRoleAssignment(role_key="trend_vol", role_label=self._role_label("trend_vol"), owner="OpenAI", product="ChatGPT", model="gpt-5", control_mode="editable", detail=detail),
            ModelRoleAssignment(role_key="flow_liquidity", role_label=self._role_label("flow_liquidity"), owner="OpenAI", product="ChatGPT", model="gpt-5", control_mode="editable", detail=detail),
            ModelRoleAssignment(role_key="oi_roll", role_label=self._role_label("oi_roll"), owner="OpenAI", product="ChatGPT", model="gpt-5", control_mode="editable", detail=detail),
            ModelRoleAssignment(role_key="macro_event", role_label=self._role_label("macro_event"), owner="OpenAI", product="ChatGPT", model="gpt-5", control_mode="editable", detail=detail),
            ModelRoleAssignment(role_key="skeptic", role_label=self._role_label("skeptic"), owner="OpenAI", product="ChatGPT", model="gpt-5", control_mode="editable", detail=detail),
            ModelRoleAssignment(role_key="arbiter", role_label=self._role_label("arbiter"), owner="OpenAI", product="ChatGPT", model="gpt-5", control_mode="editable", detail=detail),
        ]

    def _role_label(self, role_key: str) -> str:
        labels = {
            "trend_vol": "Trend / volatility analyst",
            "flow_liquidity": "Flow / liquidity analyst",
            "oi_roll": "OI / roll analyst",
            "macro_event": "Macro-event analyst",
            "skeptic": "Skeptic",
            "arbiter": "Arbiter",
        }
        return labels.get(role_key, role_key.replace("_", " ").title())
