from __future__ import annotations

from difflib import SequenceMatcher, ndiff
import json
import re
from datetime import UTC, datetime
from uuid import uuid4

from libs.dashboard.contracts import (
    ModelRoleAssignment,
    RuntimeAuditEvent,
    RuntimeControlSnapshot,
    RuntimeFreshnessPolicySnapshot,
    RuntimeFreshnessPolicyUpdate,
    RuntimePromptDiffLine,
    RuntimePromptValidationIssue,
    RuntimeModelRouteUpdate,
    RuntimeRolePromptApproveRequest,
    RuntimeRolePromptDismissRequest,
    RuntimeRolePromptDiff,
    RuntimeRolePromptProfile,
    RuntimeRolePromptRestoreRequest,
    RuntimeRolePromptUpdate,
    RuntimeRolePromptVersion,
)
from libs.domain.repository import SqlAlchemyContractMasterRepository


class _SafePromptContext(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


class RuntimeControlService:
    VARIABLE_PATTERN = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")
    APPLIED_PROMPT_ACTIONS = frozenset({"update", "restore", "reset", "approve"})
    DRAFT_PROMPT_ACTIONS = frozenset({"draft", "draft_restore"})
    APPROVAL_CRITICAL_ROLES = frozenset({"skeptic", "arbiter"})
    APPROVAL_MAJOR_REWRITE_THRESHOLD = 0.62
    APPROVAL_CRITICAL_ROLE_THRESHOLD = 0.82
    EXECUTION_PATTERNS = (
        re.compile(r"\b(place|send|submit|execute|open)\s+(an?\s+)?(order|trade|position)\b", re.IGNORECASE),
        re.compile(r"\b(buy|sell)\s+now\b", re.IGNORECASE),
        re.compile(r"\b(выстави|выставить|отправь|отправить|исполни|исполнить|купи|продай|открой)\b.*\b(приказ|заявк|сделк|позици|ордер)\b", re.IGNORECASE),
    )

    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def get_snapshot(self, *, prompt_context: dict[str, object] | None = None) -> RuntimeControlSnapshot:
        generated_at = datetime.now(UTC)
        return RuntimeControlSnapshot(
            generated_at=generated_at,
            model_routes=self.list_model_routes(),
            role_prompts=self.list_role_prompts(prompt_context=prompt_context, generated_at=generated_at),
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

    def list_role_prompts(
        self,
        *,
        prompt_context: dict[str, object] | None = None,
        generated_at: datetime | None = None,
    ) -> list[RuntimeRolePromptProfile]:
        defaults = {item.role_key: item for item in self._council_prompt_defaults_v2()}
        rows = {row.role_key: row for row in self.repository.list_runtime_role_prompts()}
        history_by_role = self._build_role_prompt_history(
            self.repository.list_runtime_audit_events(category="role_prompt", limit=250),
            defaults=defaults,
        )
        profiles: list[RuntimeRolePromptProfile] = []
        for item in defaults.values():
            effective_state = self._effective_prompt_state_from_rows(
                role_key=item.role_key,
                rows=rows,
                default_profile=item,
            )
            history = history_by_role.get(item.role_key, [])
            approved_version = self._resolve_effective_prompt_version(
                history,
                effective_state=effective_state,
            )
            pending_version = self._resolve_pending_prompt_version(
                history,
                approved_version=approved_version,
            )
            history = self._annotate_role_prompt_history(
                history,
                approved_version=approved_version,
                pending_version=pending_version,
            )
            current_state = (
                self._prompt_state_from_version(pending_version, default_profile=item)
                if pending_version is not None
                else effective_state
            )
            approval_reasons = self._role_prompt_approval_reasons(
                role_key=item.role_key,
                effective_state=effective_state,
                proposed_state=current_state,
                default_profile=item,
            )
            approval_required = bool(approval_reasons)
            profile = RuntimeRolePromptProfile(
                role_key=item.role_key,
                role_label=item.role_label,
                prompt_template=str(current_state["prompt_template"]),
                control_mode=str(current_state["control_mode"]),
                detail=self._normalize_optional_text(current_state.get("detail")),
                variables=self._extract_variables(str(current_state["prompt_template"])),
                default_prompt_template=item.prompt_template,
                current_version_id=self._resolve_current_prompt_version_id(
                    history,
                    current_state=current_state,
                )
                or (
                    pending_version.version_id
                    if pending_version is not None
                    else (approved_version.version_id if approved_version is not None else f"default:{item.role_key}")
                ),
                approved_version_id=(
                    approved_version.version_id if approved_version is not None else f"default:{item.role_key}"
                ),
                pending_version_id=pending_version.version_id if pending_version is not None else None,
                approval_required=approval_required,
                approval_state=self._resolve_role_prompt_approval_state(
                    pending_version=pending_version,
                    approval_required=approval_required,
                ),
                approval_note=self._build_role_prompt_approval_note(
                    role_label=item.role_label,
                    pending_version=pending_version,
                    approval_required=approval_required,
                    approved_version=approved_version,
                    approval_reasons=approval_reasons,
                ),
                approval_reasons=approval_reasons,
                effective_prompt_template=str(effective_state["prompt_template"]),
                effective_control_mode=str(effective_state["control_mode"]),
                version_history=history,
            )
            if prompt_context is not None:
                role_context = self._merge_role_prompt_context(prompt_context, profile)
                profile.rendered_prompt = self._render_prompt(profile.prompt_template, role_context)
                profile.effective_rendered_prompt = self._render_prompt(
                    str(profile.effective_prompt_template or profile.prompt_template),
                    role_context,
                )
            profiles.append(profile)
        return profiles

    def update_role_prompt(self, payload: RuntimeRolePromptUpdate) -> RuntimeControlSnapshot:
        default_profile = self._get_default_role_prompt(payload.role_key)
        effective_state = self._current_effective_prompt_state(payload.role_key, default_profile)
        before_state = self._current_working_prompt_state(payload.role_key, default_profile)
        after_state = self._normalize_prompt_state(
            {
                "role_key": payload.role_key,
                "prompt_template": payload.prompt_template,
                "control_mode": payload.control_mode,
                "detail": payload.detail,
            },
            default_profile=default_profile,
        )
        self._ensure_role_prompt_can_save(
            self._prompt_profile_from_state(after_state, default_profile=default_profile),
            default_profile=default_profile,
        )
        approval_reasons = self._role_prompt_approval_reasons(
            role_key=payload.role_key,
            effective_state=effective_state,
            proposed_state=after_state,
            default_profile=default_profile,
        )
        requires_approval = bool(approval_reasons)
        release_note = self._build_prompt_release_note(
            before_state=before_state,
            after_state=after_state,
            action="draft" if requires_approval else "update",
            approval_reasons=approval_reasons,
        )
        if requires_approval:
            self._record_audit(
                category="role_prompt",
                action="draft",
                target_key=payload.role_key,
                detail=f"Saved council prompt draft for {payload.role_key}.",
                payload={
                    "role_key": payload.role_key,
                    "summary": "Saved council prompt draft pending approval.",
                    "before": before_state,
                    "effective_before": effective_state,
                    "after": after_state,
                    "approval_state": "pending_approval",
                    "approval_reasons": approval_reasons,
                    "release_note": release_note,
                },
            )
            return self.get_snapshot()

        updated_at = datetime.now(UTC)
        self.repository.upsert_runtime_role_prompt(
            role_key=payload.role_key,
            prompt_template=str(after_state["prompt_template"]),
            control_mode=str(after_state["control_mode"]),
            detail=self._normalize_optional_text(after_state.get("detail")),
            updated_at=updated_at,
        )
        self._record_audit(
            category="role_prompt",
            action="update",
            target_key=payload.role_key,
            detail=f"Updated council prompt for {payload.role_key}.",
            payload={
                "role_key": payload.role_key,
                "summary": "Saved council prompt update.",
                "before": before_state,
                "effective_before": effective_state,
                "after": after_state,
                "release_note": release_note,
            },
        )
        return self.get_snapshot()

    def reset_role_prompts(self) -> RuntimeControlSnapshot:
        defaults = self._council_prompt_defaults_v2()
        current_rows = {row.role_key: row for row in self.repository.list_runtime_role_prompts()}
        self.repository.delete_runtime_role_prompts()
        for item in defaults:
            before_state = (
                self._prompt_state_from_row(current_rows[item.role_key])
                if item.role_key in current_rows
                else self._prompt_state_from_profile(item)
            )
            after_state = self._prompt_state_from_profile(item)
            self.repository.upsert_runtime_role_prompt(
                role_key=item.role_key,
                prompt_template=item.prompt_template,
                control_mode=item.control_mode,
                detail=item.detail,
                updated_at=datetime.now(UTC),
            )
            self._record_audit(
                category="role_prompt",
                action="reset",
                target_key=item.role_key,
                detail=f"Reset council prompt for {item.role_key} to default.",
                payload={
                    "role_key": item.role_key,
                    "summary": "Reset council prompt to built-in default.",
                    "restored_from_version_id": f"default:{item.role_key}",
                    "before": before_state,
                    "after": after_state,
                    "release_note": self._build_prompt_release_note(
                        before_state=before_state,
                        after_state=after_state,
                        action="reset",
                    ),
                },
            )
        return self.get_snapshot()

    def preview_role_prompt_diff(
        self,
        payload: RuntimeRolePromptUpdate,
        *,
        prompt_context: dict[str, object] | None = None,
    ) -> RuntimeRolePromptDiff:
        default_profile = self._get_default_role_prompt(payload.role_key)
        effective_state = self._current_effective_prompt_state(payload.role_key, default_profile)
        effective_history = self._list_role_prompt_history(payload.role_key, default_profile)
        approved_version = self._resolve_effective_prompt_version(
            effective_history,
            effective_state=effective_state,
        )
        before_state = self._current_working_prompt_state(payload.role_key, default_profile)
        before_profile = self._prompt_profile_from_state(
            before_state,
            default_profile=default_profile,
        )
        after_state = self._normalize_prompt_state(
            {
                "role_key": payload.role_key,
                "prompt_template": payload.prompt_template,
                "control_mode": payload.control_mode,
                "detail": payload.detail,
            },
            default_profile=default_profile,
        )
        after_profile = self._prompt_profile_from_state(
            after_state,
            default_profile=default_profile,
        )
        metadata_changes: list[str] = []
        if before_profile.control_mode != after_profile.control_mode:
            metadata_changes.append(
                f"control_mode: {before_profile.control_mode} -> {after_profile.control_mode}"
            )
        if (before_profile.detail or "") != (after_profile.detail or ""):
            metadata_changes.append("detail updated")

        diff_lines: list[RuntimePromptDiffLine] = []
        added = 0
        removed = 0
        for line in ndiff(
            before_profile.prompt_template.splitlines(),
            after_profile.prompt_template.splitlines(),
        ):
            if line.startswith("? "):
                continue
            kind = "context"
            if line.startswith("+ "):
                kind = "add"
                added += 1
            elif line.startswith("- "):
                kind = "remove"
                removed += 1
            diff_lines.append(RuntimePromptDiffLine(kind=kind, text=line[2:]))

        unresolved_variables: list[str] = []
        before_rendered_prompt: str | None = None
        after_rendered_prompt: str | None = None
        if prompt_context is not None:
            before_context = self._merge_role_prompt_context(prompt_context, before_profile)
            after_context = self._merge_role_prompt_context(prompt_context, after_profile)
            before_rendered_prompt = self._render_prompt(before_profile.prompt_template, before_context)
            after_rendered_prompt = self._render_prompt(after_profile.prompt_template, after_context)
            unresolved_variables = [
                variable
                for variable in after_profile.variables
                if variable not in after_context
            ]
        validation_issues = self._validate_role_prompt_profile(
            after_profile,
            default_profile=default_profile,
            unresolved_variables=unresolved_variables,
        )
        can_save = not any(item.severity == "blocking" for item in validation_issues)
        approval_reasons = self._role_prompt_approval_reasons(
            role_key=payload.role_key,
            effective_state=effective_state,
            proposed_state=after_state,
            default_profile=default_profile,
        )
        release_note_preview = self._build_prompt_release_note(
            before_state=effective_state,
            after_state=after_state,
            action="draft" if approval_reasons else "update",
            approval_reasons=approval_reasons,
        )

        has_changes = (
            before_profile.prompt_template != after_profile.prompt_template
            or bool(metadata_changes)
        )
        summary_parts: list[str] = []
        if before_profile.prompt_template != after_profile.prompt_template:
            summary_parts.append(f"template lines +{added} / -{removed}")
        if metadata_changes:
            summary_parts.append(f"{len(metadata_changes)} metadata change(s)")
        if unresolved_variables:
            summary_parts.append(f"{len(unresolved_variables)} unresolved variable(s)")
        if validation_issues:
            blocking = sum(1 for item in validation_issues if item.severity == "blocking")
            warnings = sum(1 for item in validation_issues if item.severity != "blocking")
            if blocking:
                summary_parts.append(f"{blocking} blocking issue(s)")
            if warnings:
                summary_parts.append(f"{warnings} warning(s)")
        if approval_reasons:
            summary_parts.append(f"{len(approval_reasons)} approval trigger(s)")
        summary = (
            "; ".join(summary_parts)
            if summary_parts
            else "No changes relative to the current saved prompt."
        )
        return RuntimeRolePromptDiff(
            role_key=payload.role_key,
            role_label=default_profile.role_label,
            has_changes=has_changes,
            can_save=can_save,
            approval_required=bool(approval_reasons),
            summary=summary,
            baseline_version_id=(
                approved_version.version_id if approved_version is not None else f"default:{payload.role_key}"
            ),
            baseline_label=(
                "approved_version" if approved_version is not None else "built_in_default"
            ),
            release_note_preview=release_note_preview,
            metadata_changes=metadata_changes,
            approval_reasons=approval_reasons,
            unresolved_variables=unresolved_variables,
            validation_issues=validation_issues,
            lines=diff_lines,
            before_rendered_prompt=before_rendered_prompt,
            after_rendered_prompt=after_rendered_prompt,
        )

    def restore_role_prompt(self, payload: RuntimeRolePromptRestoreRequest) -> RuntimeControlSnapshot:
        default_profile = self._get_default_role_prompt(payload.role_key)
        effective_state = self._current_effective_prompt_state(payload.role_key, default_profile)
        before_state = self._current_working_prompt_state(payload.role_key, default_profile)
        restored_from_version_id = payload.version_id
        if payload.version_id == f"default:{payload.role_key}":
            after_state = self._prompt_state_from_profile(default_profile)
        else:
            event = self.repository.get_runtime_audit_event(payload.version_id)
            if event is None or event.category != "role_prompt" or event.target_key != payload.role_key:
                raise ValueError(f"Prompt version {payload.version_id} is not available for {payload.role_key}.")
            payload_body = self._decode_audit_payload(event.payload_json)
            restored_state = self._prompt_state_from_audit_payload(
                payload_body,
                default_profile=default_profile,
            )
            if restored_state is None:
                raise ValueError(f"Prompt version {payload.version_id} does not contain a restorable prompt snapshot.")
            after_state = restored_state
        self._ensure_role_prompt_can_save(
            self._prompt_profile_from_state(after_state, default_profile=default_profile),
            default_profile=default_profile,
        )
        approval_reasons = self._role_prompt_approval_reasons(
            role_key=payload.role_key,
            effective_state=effective_state,
            proposed_state=after_state,
            default_profile=default_profile,
        )
        requires_approval = bool(approval_reasons)
        release_note = self._build_prompt_release_note(
            before_state=before_state,
            after_state=after_state,
            action="draft_restore" if requires_approval else "restore",
            restored_from_version_id=restored_from_version_id,
            approval_reasons=approval_reasons,
        )
        if requires_approval and not self._prompt_states_match(effective_state, after_state):
            self._record_audit(
                category="role_prompt",
                action="draft_restore",
                target_key=payload.role_key,
                detail=f"Restored council prompt draft for {payload.role_key}.",
                payload={
                    "role_key": payload.role_key,
                    "summary": "Restored council prompt into a draft pending approval.",
                    "restored_from_version_id": restored_from_version_id,
                    "before": before_state,
                    "effective_before": effective_state,
                    "after": after_state,
                    "approval_state": "pending_approval",
                    "approval_reasons": approval_reasons,
                    "release_note": release_note,
                },
            )
            return self.get_snapshot()
        self.repository.upsert_runtime_role_prompt(
            role_key=payload.role_key,
            prompt_template=str(after_state["prompt_template"]),
            control_mode=str(after_state["control_mode"]),
            detail=self._normalize_optional_text(after_state.get("detail")),
            updated_at=datetime.now(UTC),
        )
        self._record_audit(
            category="role_prompt",
            action="restore",
            target_key=payload.role_key,
            detail=f"Restored council prompt for {payload.role_key}.",
            payload={
                "role_key": payload.role_key,
                "summary": "Restored council prompt from history.",
                "restored_from_version_id": restored_from_version_id,
                "before": before_state,
                "effective_before": effective_state,
                "after": after_state,
                "release_note": release_note,
            },
        )
        return self.get_snapshot()

    def approve_role_prompt(self, payload: RuntimeRolePromptApproveRequest) -> RuntimeControlSnapshot:
        default_profile = self._get_default_role_prompt(payload.role_key)
        effective_state = self._current_effective_prompt_state(payload.role_key, default_profile)
        history = self._list_role_prompt_history(payload.role_key, default_profile)
        approved_version = self._resolve_effective_prompt_version(history, effective_state=effective_state)
        pending_version = self._resolve_pending_prompt_version(history, approved_version=approved_version)
        if pending_version is None:
            raise ValueError(f"No pending council prompt draft is available for {payload.role_key}.")
        if payload.version_id is not None and payload.version_id != pending_version.version_id:
            raise ValueError(
                f"Only the latest pending draft for {payload.role_key} can be approved."
            )

        after_state = self._prompt_state_from_version(pending_version, default_profile=default_profile)
        self._ensure_role_prompt_can_save(
            self._prompt_profile_from_state(after_state, default_profile=default_profile),
            default_profile=default_profile,
        )
        release_note = self._build_prompt_release_note(
            before_state=effective_state,
            after_state=after_state,
            action="approve",
            approval_reasons=[],
        )
        self.repository.upsert_runtime_role_prompt(
            role_key=payload.role_key,
            prompt_template=str(after_state["prompt_template"]),
            control_mode=str(after_state["control_mode"]),
            detail=self._normalize_optional_text(after_state.get("detail")),
            updated_at=datetime.now(UTC),
        )
        self._record_audit(
            category="role_prompt",
            action="approve",
            target_key=payload.role_key,
            detail=f"Approved council prompt draft for {payload.role_key}.",
            payload={
                "role_key": payload.role_key,
                "summary": "Approved council prompt draft and made it effective.",
                "approved_from_version_id": pending_version.version_id,
                "before": effective_state,
                "after": after_state,
                "release_note": release_note,
            },
        )
        return self.get_snapshot()

    def dismiss_role_prompt(self, payload: RuntimeRolePromptDismissRequest) -> RuntimeControlSnapshot:
        default_profile = self._get_default_role_prompt(payload.role_key)
        effective_state = self._current_effective_prompt_state(payload.role_key, default_profile)
        before_state = self._current_working_prompt_state(payload.role_key, default_profile)
        history = self._list_role_prompt_history(payload.role_key, default_profile)
        approved_version = self._resolve_effective_prompt_version(history, effective_state=effective_state)
        pending_version = self._resolve_pending_prompt_version(history, approved_version=approved_version)
        if pending_version is None:
            raise ValueError(f"No pending council prompt draft is available for {payload.role_key}.")
        if payload.version_id is not None and payload.version_id != pending_version.version_id:
            raise ValueError(
                f"Only the latest pending draft for {payload.role_key} can be dismissed."
            )

        dismissed_state = self._prompt_state_from_version(pending_version, default_profile=default_profile)
        release_note = self._build_prompt_release_note(
            before_state=dismissed_state,
            after_state=effective_state,
            action="dismiss",
        )
        self._record_audit(
            category="role_prompt",
            action="dismiss",
            target_key=payload.role_key,
            detail=f"Dismissed council prompt draft for {payload.role_key}.",
            payload={
                "role_key": payload.role_key,
                "summary": "Dismissed pending council prompt draft.",
                "dismissed_version_id": pending_version.version_id,
                "before": before_state,
                "dismissed": dismissed_state,
                "effective_before": effective_state,
                "after": effective_state,
                "release_note": release_note,
            },
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

    def _build_role_prompt_history(
        self,
        rows: list[object],
        *,
        defaults: dict[str, RuntimeRolePromptProfile],
    ) -> dict[str, list[RuntimeRolePromptVersion]]:
        history_by_role = {role_key: [] for role_key in defaults}
        for row in rows:
            role_key = getattr(row, "target_key", None)
            if role_key not in defaults:
                continue
            payload = self._decode_audit_payload(getattr(row, "payload_json", "{}"))
            state = self._prompt_state_from_audit_payload(payload, default_profile=defaults[role_key])
            if state is None:
                continue
            history_by_role[role_key].append(
                RuntimeRolePromptVersion(
                    version_id=getattr(row, "event_id"),
                    action=getattr(row, "action"),
                    summary=str(payload.get("summary") or getattr(row, "detail")),
                    prompt_template=str(state["prompt_template"]),
                    control_mode=str(state["control_mode"]),
                    detail=self._normalize_optional_text(state.get("detail")),
                    created_at=getattr(row, "created_at"),
                    lifecycle_state="history",
                    release_note=self._normalize_optional_text(payload.get("release_note")),
                    dismissed_version_id=self._normalize_optional_text(payload.get("dismissed_version_id")),
                    restored_from_version_id=self._normalize_optional_text(payload.get("restored_from_version_id")),
                    restorable=True,
                )
            )
        return history_by_role

    def _current_effective_prompt_state(
        self,
        role_key: str,
        default_profile: RuntimeRolePromptProfile,
    ) -> dict[str, object]:
        current_rows = {row.role_key: row for row in self.repository.list_runtime_role_prompts()}
        return self._effective_prompt_state_from_rows(
            role_key=role_key,
            rows=current_rows,
            default_profile=default_profile,
        )

    def _current_working_prompt_state(
        self,
        role_key: str,
        default_profile: RuntimeRolePromptProfile,
    ) -> dict[str, object]:
        effective_state = self._current_effective_prompt_state(role_key, default_profile)
        history = self._list_role_prompt_history(role_key, default_profile)
        approved_version = self._resolve_effective_prompt_version(history, effective_state=effective_state)
        pending_version = self._resolve_pending_prompt_version(history, approved_version=approved_version)
        if pending_version is None:
            return effective_state
        return self._prompt_state_from_version(pending_version, default_profile=default_profile)

    def _effective_prompt_state_from_rows(
        self,
        *,
        role_key: str,
        rows: dict[str, object],
        default_profile: RuntimeRolePromptProfile,
    ) -> dict[str, object]:
        row = rows.get(role_key)
        return self._prompt_state_from_row(row) if row is not None else self._prompt_state_from_profile(default_profile)

    def _list_role_prompt_history(
        self,
        role_key: str,
        default_profile: RuntimeRolePromptProfile,
    ) -> list[RuntimeRolePromptVersion]:
        return self._build_role_prompt_history(
            self.repository.list_runtime_audit_events(
                category="role_prompt",
                target_key=role_key,
                limit=100,
            ),
            defaults={role_key: default_profile},
        ).get(role_key, [])

    def _get_default_role_prompt(self, role_key: str) -> RuntimeRolePromptProfile:
        for item in self._council_prompt_defaults_v2():
            if item.role_key == role_key:
                return item
        raise ValueError(f"Unknown council role prompt: {role_key}")

    def _prompt_profile_from_state(
        self,
        state: dict[str, object],
        *,
        default_profile: RuntimeRolePromptProfile,
    ) -> RuntimeRolePromptProfile:
        normalized = self._normalize_prompt_state(state, default_profile=default_profile)
        return RuntimeRolePromptProfile(
            role_key=default_profile.role_key,
            role_label=default_profile.role_label,
            prompt_template=str(normalized["prompt_template"]),
            control_mode=str(normalized["control_mode"]),
            detail=self._normalize_optional_text(normalized.get("detail")),
            variables=self._extract_variables(str(normalized["prompt_template"])),
            default_prompt_template=default_profile.prompt_template,
        )

    def _resolve_current_prompt_version_id(
        self,
        history: list[RuntimeRolePromptVersion],
        *,
        current_state: dict[str, object],
    ) -> str | None:
        for item in history:
            if self._prompt_version_matches_state(item, current_state=current_state):
                return item.version_id
        return None

    def _resolve_effective_prompt_version(
        self,
        history: list[RuntimeRolePromptVersion],
        *,
        effective_state: dict[str, object],
    ) -> RuntimeRolePromptVersion | None:
        for item in history:
            if item.action not in self.APPLIED_PROMPT_ACTIONS:
                continue
            if self._prompt_version_matches_state(item, current_state=effective_state):
                return item
        return None

    def _resolve_pending_prompt_version(
        self,
        history: list[RuntimeRolePromptVersion],
        *,
        approved_version: RuntimeRolePromptVersion | None,
    ) -> RuntimeRolePromptVersion | None:
        approved_at = approved_version.created_at if approved_version is not None else None
        dismissed_version_ids = {
            item.dismissed_version_id
            for item in history
            if item.action == "dismiss" and item.dismissed_version_id
        }
        for item in history:
            if item.action not in self.DRAFT_PROMPT_ACTIONS:
                continue
            if item.version_id in dismissed_version_ids:
                continue
            if approved_at is not None and item.created_at <= approved_at:
                continue
            return item
        return None

    def _annotate_role_prompt_history(
        self,
        history: list[RuntimeRolePromptVersion],
        *,
        approved_version: RuntimeRolePromptVersion | None,
        pending_version: RuntimeRolePromptVersion | None,
    ) -> list[RuntimeRolePromptVersion]:
        approved_version_id = approved_version.version_id if approved_version is not None else None
        pending_version_id = pending_version.version_id if pending_version is not None else None
        annotated: list[RuntimeRolePromptVersion] = []
        for item in history:
            lifecycle_state = "superseded"
            if item.action == "dismiss":
                lifecycle_state = "dismissed"
            elif pending_version_id is not None and item.version_id == pending_version_id:
                lifecycle_state = "draft"
            elif approved_version_id is not None and item.version_id == approved_version_id:
                lifecycle_state = "approved"
            annotated.append(
                item.model_copy(
                    update={
                        "lifecycle_state": lifecycle_state,
                    }
                )
            )
        return annotated

    def _prompt_version_matches_state(
        self,
        item: RuntimeRolePromptVersion,
        *,
        current_state: dict[str, object],
    ) -> bool:
        return (
            item.prompt_template == str(current_state["prompt_template"])
            and item.control_mode == str(current_state["control_mode"])
            and (item.detail or "") == (self._normalize_optional_text(current_state.get("detail")) or "")
        )

    def _prompt_state_from_version(
        self,
        version: RuntimeRolePromptVersion,
        *,
        default_profile: RuntimeRolePromptProfile,
    ) -> dict[str, object]:
        return self._normalize_prompt_state(
            {
                "role_key": default_profile.role_key,
                "prompt_template": version.prompt_template,
                "control_mode": version.control_mode,
                "detail": version.detail,
            },
            default_profile=default_profile,
        )

    def _build_prompt_release_note(
        self,
        *,
        before_state: dict[str, object],
        after_state: dict[str, object],
        action: str,
        restored_from_version_id: str | None = None,
        approval_reasons: list[str] | None = None,
    ) -> str:
        notes: list[str] = []
        before_mode = str(before_state.get("control_mode") or "editable")
        after_mode = str(after_state.get("control_mode") or "editable")
        before_template = str(before_state.get("prompt_template") or "")
        after_template = str(after_state.get("prompt_template") or "")
        before_vars = set(self._extract_variables(before_template))
        after_vars = set(self._extract_variables(after_template))
        if before_mode != after_mode:
            notes.append(f"mode {before_mode}->{after_mode}")
        if before_vars != after_vars:
            notes.append("placeholder surface changed")
        if before_template != after_template:
            added = max(0, len(after_template.splitlines()) - len(before_template.splitlines()))
            removed = max(0, len(before_template.splitlines()) - len(after_template.splitlines()))
            notes.append(f"template delta +{added}/-{removed}")
        if action == "reset":
            notes = ["returned to built-in default"]
        elif action == "restore":
            notes.insert(0, f"restored from {restored_from_version_id or 'history'}")
        elif action == "draft_restore":
            notes.insert(0, f"draft restored from {restored_from_version_id or 'history'}")
        elif action == "approve":
            notes.insert(0, "draft promoted to approved")
        elif action == "dismiss":
            notes.insert(0, "pending draft dismissed")
        elif action == "draft":
            notes.insert(0, "saved as pending draft")
        elif action == "update":
            notes.insert(0, "saved as live prompt")
        if approval_reasons:
            notes.append(f"approval: {'; '.join(approval_reasons[:2])}")
        return "; ".join(dict.fromkeys(note for note in notes if note))

    def _role_prompt_approval_reasons(
        self,
        *,
        role_key: str,
        effective_state: dict[str, object],
        proposed_state: dict[str, object],
        default_profile: RuntimeRolePromptProfile,
    ) -> list[str]:
        effective_mode = str(effective_state.get("control_mode") or "editable")
        proposed_mode = str(proposed_state.get("control_mode") or "editable")
        reasons: list[str] = []
        effective_is_default = self._prompt_states_match(
            effective_state,
            self._prompt_state_from_profile(default_profile),
        )
        if effective_mode == "fixed" or proposed_mode == "fixed":
            reasons.append("Fixed-mode prompts require explicit approval before they become effective.")
        if effective_mode != proposed_mode:
            reasons.append("Changing control mode changes council guardrails and requires approval.")

        effective_template = str(effective_state.get("prompt_template") or "")
        proposed_template = str(proposed_state.get("prompt_template") or "")
        if effective_template != proposed_template:
            drift_ratio = SequenceMatcher(
                None,
                effective_template.strip(),
                proposed_template.strip(),
            ).ratio()
            if not effective_is_default:
                if set(self._extract_variables(effective_template)) != set(self._extract_variables(proposed_template)):
                    reasons.append("Changing the placeholder surface changes the council input packet and requires approval.")
                if (
                    role_key in self.APPROVAL_CRITICAL_ROLES
                    and drift_ratio < self.APPROVAL_CRITICAL_ROLE_THRESHOLD
                ):
                    reasons.append(
                        "This is a major rewrite for a council-critical role and should be explicitly approved."
                    )
                elif drift_ratio < self.APPROVAL_MAJOR_REWRITE_THRESHOLD:
                    reasons.append("This draft materially rewrites the saved prompt and should be explicitly approved.")

        return list(dict.fromkeys(reasons))

    def _resolve_role_prompt_approval_state(
        self,
        *,
        pending_version: RuntimeRolePromptVersion | None,
        approval_required: bool,
    ) -> str:
        if pending_version is not None:
            return "pending_approval"
        if approval_required:
            return "approved"
        return "live"

    def _build_role_prompt_approval_note(
        self,
        *,
        role_label: str,
        pending_version: RuntimeRolePromptVersion | None,
        approval_required: bool,
        approved_version: RuntimeRolePromptVersion | None,
        approval_reasons: list[str],
    ) -> str | None:
        if pending_version is not None:
            approved_id = approved_version.version_id if approved_version is not None else "default"
            trigger_note = f" Triggers: {'; '.join(approval_reasons)}" if approval_reasons else ""
            return (
                f"{role_label} is still using approved version {approved_id}; "
                f"the latest draft must be approved before it becomes effective.{trigger_note}"
            )
        if approval_required:
            trigger_note = f" Triggers: {'; '.join(approval_reasons)}" if approval_reasons else ""
            return (
                f"{role_label} is locked to an approved prompt. New changes stay in draft until approval.{trigger_note}"
            )
        return "Editable prompt changes become effective right after save."

    def _prompt_states_match(
        self,
        left: dict[str, object],
        right: dict[str, object],
    ) -> bool:
        return (
            str(left.get("prompt_template")) == str(right.get("prompt_template"))
            and str(left.get("control_mode")) == str(right.get("control_mode"))
            and (self._normalize_optional_text(left.get("detail")) or "")
            == (self._normalize_optional_text(right.get("detail")) or "")
        )

    def _prompt_state_from_row(self, row: object) -> dict[str, object]:
        return {
            "role_key": getattr(row, "role_key"),
            "prompt_template": getattr(row, "prompt_template"),
            "control_mode": getattr(row, "control_mode"),
            "detail": getattr(row, "detail"),
        }

    def _prompt_state_from_profile(self, profile: RuntimeRolePromptProfile) -> dict[str, object]:
        return {
            "role_key": profile.role_key,
            "prompt_template": profile.prompt_template,
            "control_mode": profile.control_mode,
            "detail": profile.detail,
        }

    def _prompt_state_from_audit_payload(
        self,
        payload: dict[str, object],
        *,
        default_profile: RuntimeRolePromptProfile,
    ) -> dict[str, object] | None:
        dismissed = payload.get("dismissed")
        if isinstance(dismissed, dict):
            return self._normalize_prompt_state(dismissed, default_profile=default_profile)
        after = payload.get("after")
        if isinstance(after, dict):
            return self._normalize_prompt_state(after, default_profile=default_profile)
        if "prompt_template" in payload:
            return self._normalize_prompt_state(payload, default_profile=default_profile)
        return None

    def _normalize_prompt_state(
        self,
        state: dict[str, object],
        *,
        default_profile: RuntimeRolePromptProfile,
    ) -> dict[str, object]:
        prompt_template = state.get("prompt_template")
        control_mode = state.get("control_mode")
        detail = state.get("detail")
        return {
            "role_key": str(state.get("role_key") or default_profile.role_key),
            "prompt_template": str(
                prompt_template if prompt_template not in (None, "") else default_profile.prompt_template
            ),
            "control_mode": str(
                control_mode if control_mode not in (None, "") else default_profile.control_mode
            ),
            "detail": self._normalize_optional_text(detail),
        }

    def _normalize_optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _decode_audit_payload(self, payload_json: str) -> dict[str, object]:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _ensure_role_prompt_can_save(
        self,
        profile: RuntimeRolePromptProfile,
        *,
        default_profile: RuntimeRolePromptProfile,
    ) -> None:
        issues = self._validate_role_prompt_profile(profile, default_profile=default_profile)
        blocking_messages = [item.message for item in issues if item.severity == "blocking"]
        if blocking_messages:
            raise ValueError(" ".join(blocking_messages))

    def _validate_role_prompt_profile(
        self,
        profile: RuntimeRolePromptProfile,
        *,
        default_profile: RuntimeRolePromptProfile,
        unresolved_variables: list[str] | None = None,
    ) -> list[RuntimePromptValidationIssue]:
        issues: list[RuntimePromptValidationIssue] = []
        allowed_modes = {"editable", "fixed"}
        if profile.control_mode not in allowed_modes:
            issues.append(
                RuntimePromptValidationIssue(
                    code="invalid_control_mode",
                    severity="blocking",
                    message=f"Control mode must stay within {sorted(allowed_modes)}.",
                )
            )

        non_empty_lines = [line.strip() for line in profile.prompt_template.splitlines() if line.strip()]
        if len(non_empty_lines) < 3:
            issues.append(
                RuntimePromptValidationIssue(
                    code="prompt_too_short",
                    severity="blocking",
                    message="Prompt is too short to preserve role context and guardrails.",
                )
            )

        current_variables = set(profile.variables)
        missing_protected = [
            item for item in self._protected_role_placeholders(profile.role_key) if item not in current_variables
        ]
        if missing_protected:
            issues.append(
                RuntimePromptValidationIssue(
                    code="missing_protected_placeholders",
                    severity="blocking",
                    message=f"Prompt must keep protected placeholders: {', '.join(missing_protected)}.",
                )
            )

        unsupported_variables = sorted(current_variables - self._allowed_prompt_variables())
        if unsupported_variables:
            issues.append(
                RuntimePromptValidationIssue(
                    code="unsupported_placeholders",
                    severity="blocking",
                    message=f"Prompt uses unsupported placeholders: {', '.join(unsupported_variables)}.",
                )
            )

        unresolved = sorted(set(unresolved_variables or []))
        if unresolved:
            issues.append(
                RuntimePromptValidationIssue(
                    code="unresolved_placeholders",
                    severity="blocking",
                    message=f"Prompt still contains unresolved placeholders for live render: {', '.join(unresolved)}.",
                )
            )

        lowered_template = profile.prompt_template.lower()
        for pattern in self.EXECUTION_PATTERNS:
            if pattern.search(lowered_template):
                issues.append(
                    RuntimePromptValidationIssue(
                        code="execution_instruction",
                        severity="blocking",
                        message="Prompt must remain decision-support only and cannot instruct execution or order placement.",
                    )
                )
                break

        drift_ratio = SequenceMatcher(
            None,
            default_profile.prompt_template.strip(),
            profile.prompt_template.strip(),
        ).ratio()
        if drift_ratio < 0.4:
            issues.append(
                RuntimePromptValidationIssue(
                    code="default_drift",
                    severity="warning",
                    message="Draft drifts far from the built-in default. Review the role intent before saving.",
                )
            )
        if profile.control_mode == "fixed" and drift_ratio < 0.55:
            issues.append(
                RuntimePromptValidationIssue(
                    code="fixed_mode_review",
                    severity="warning",
                    message="This role is moving to fixed mode with a materially changed prompt. Prefer editable unless the template is intentionally locked.",
                )
            )
        return issues

    def _protected_role_placeholders(self, role_key: str) -> list[str]:
        base = ["role_label", "root_code", "signal_summary", "role_context_packet"]
        mapping = {
            "trend_vol": base,
            "flow_liquidity": base,
            "oi_roll": [*base, "active_contract", "next_contract"],
            "macro_event": [*base, "session_type"],
            "skeptic": [*base, "confidence_final", "skeptic_score"],
            "arbiter": [*base, "confidence_final", "skeptic_score"],
        }
        return mapping.get(role_key, base)

    def _allowed_prompt_variables(self) -> set[str]:
        return {
            "root_code",
            "active_contract",
            "next_contract",
            "contract_code",
            "horizon",
            "session_type",
            "trading_day",
            "current_price",
            "price_change_pct",
            "workflow_state",
            "signal_direction",
            "signal_status",
            "signal_summary",
            "why_now",
            "pushback",
            "invalidation",
            "data_mode",
            "price_source",
            "roll_state",
            "reference_status",
            "days_to_expiry",
            "roll_share",
            "confidence_final",
            "skeptic_score",
            "role_label",
            "role_key",
            "role_context_packet",
        }

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

    def _merge_role_prompt_context(
        self,
        prompt_context: dict[str, object],
        profile: RuntimeRolePromptProfile,
    ) -> dict[str, object]:
        role_context = {
            key: value
            for key, value in prompt_context.items()
            if key != "role_context_packets"
        }
        role_context.update(
            {
                "role_key": profile.role_key,
                "role_label": profile.role_label,
                "role_context_packet": "",
            }
        )
        role_packets = prompt_context.get("role_context_packets")
        if isinstance(role_packets, dict):
            resolved_packet = role_packets.get(profile.role_key)
            if isinstance(resolved_packet, dict):
                role_context.update(resolved_packet)
                if "role_context_packet" not in resolved_packet:
                    role_context["role_context_packet"] = ""
            elif resolved_packet is not None:
                role_context["role_context_packet"] = resolved_packet
        return role_context

    def _council_prompt_defaults_v2(self) -> list[RuntimeRolePromptProfile]:
        detail = "Editable council prompt template with role-scoped workspace placeholders."

        templates = {
            "trend_vol": """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт: {contract_code}.
Базовый тезис: {signal_summary}

Релевантный packet роли:
{role_context_packet}

Твоя задача:
1. Оцени, есть ли на горизонте направленный режим или перед нами шум.
2. Отдели устойчивое движение от случайного выброса и скажи, помогает ли текущая волатильность сценарию.
3. Назови главный риск слома тезиса и один признак, который сильнее всего укрепит доверие.

Жёсткие правила:
- Не выдумывай данные, которых нет во входе.
- Не давай команд на сделку, автоторговлю или order routing.
- Если данных недостаточно, прямо скажи об этом.

Ответ верни строго в блоках:
verdict: support | caution | oppose
regime:
why_now:
primary_risk:
what_changes_mind:
confidence_note:
            """.strip(),
            "flow_liquidity": """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт: {contract_code}.
Базовый тезис: {signal_summary}

Релевантный packet роли:
{role_context_packet}

Твоя задача:
1. Оцени, выглядит ли движение подтверждённым потоком и ликвидностью или оно хрупкое.
2. Отдели чистое участие рынка от тонкого рынка, проскальзывания и искажённой реакции.
3. Скажи, что именно надо подтвердить, чтобы движению можно было доверять сильнее.

Жёсткие правила:
- Не подменяй отсутствие данных догадками.
- Не предлагай order routing и не описывай исполнение как готовую команду.
- Если качество потока нельзя оценить надёжно, пометь это явно.

Ответ верни строго в блоках:
verdict: support | caution | oppose
liquidity_state: clean | mixed | thin
trust_in_move:
execution_risk:
fragility_signal:
what_needs_confirmation:
            """.strip(),
            "oi_roll": """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; серия: {active_contract} -> {next_contract}.
Базовый тезис: {signal_summary}

Релевантный packet роли:
{role_context_packet}

Твоя задача:
1. Оцени, насколько текущий контракт и переход между контрактами загрязняют сигнал.
2. Отдельно проговори риск expiry pressure и риск неверного чтения OI/ролла.
3. Скажи, какое наблюдение уменьшит сомнение по серии сильнее всего.

Жёсткие правила:
- Не выдумывай OI, календарный спред или roll-метрики, которых нет во входе.
- Не своди анализ к общим словам, если риск связан с конкретной фазой ролла.
- Не давай торговых инструкций.

Ответ верни строго в блоках:
verdict: support | caution | oppose
roll_state_assessment: clean | transitional | contaminated
expiry_pressure: low | medium | high
contamination_risk:
break_point:
what_reduces_risk:
            """.strip(),
            "macro_event": """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; торговый день: {trading_day}.
Базовый тезис: {signal_summary}

Релевантный packet роли:
{role_context_packet}

Твоя задача:
1. Оцени, насколько ближайший макро- и событийный контекст совместим с текущим тезисом.
2. Скажи, что именно может быстро сломать идею даже при нормальной цене.
3. Назови один фактор, который снизит event risk и позволит доверять сценарию сильнее.

Жёсткие правила:
- Не придумывай конкретные события, если их нет во входе.
- Не подменяй оценку event risk общим рыночным фоном.
- Не давай торговых команд и не обещай результат.

Ответ верни строго в блоках:
verdict: support | caution | oppose
event_regime: clean | fragile | blocked
event_risk:
why_this_can_break:
what_derisks_it:
watch_next:
            """.strip(),
            "skeptic": """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт: {contract_code}.
Базовый тезис: {signal_summary}

Релевантный packet роли:
{role_context_packet}

Твоя задача:
1. Сначала ищи сильнейший сценарий отказа, а не подтверждение идеи.
2. Найди структурную слабость тезиса, недостающее доказательство и место, где авторы могут обманываться шумом.
3. Если идея всё же выживает, коротко скажи, что именно её спасает.

Жёсткие правила:
- Не смягчай формулировки ради согласия с остальными участниками.
- Не повторяй вход как пересказ; выделяй только реальные уязвимости.
- Не давай order routing и не предлагай автоматическое действие.

Ответ верни строго в блоках:
skeptic_verdict: pass | soft_fail | reject | human_review
strongest_rejection_case:
weak_point:
missing_evidence:
what_would_rescue_setup:
bottom_line:
            """.strip(),
            "arbiter": """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт: {contract_code}.
Базовый тезис: {signal_summary}

Релевантный packet роли:
{role_context_packet}

Твоя задача:
1. Собери выводы совета в один понятный человеческий итог.
2. Разведи, что у идеи реально сильное, а что пока не даёт поднять уверенность.
3. Скажи, что именно пользователю стоит наблюдать следующим, прежде чем усиливать доверие к сценарию.

Жёсткие правила:
- Не выдумывай мнения участников, которых нет во входе.
- Не превращай итог в команду на сделку или автоторговлю.
- Если уверенность ограничена, это должно быть видно прямо в вердикте.

Ответ верни строго в блоках:
final_call: bullish | bearish | no_edge
confidence_band: low | medium | high
why_now:
what_blocks_conviction:
what_user_should_watch_next:
publication_verdict: publish | downrank | hold_for_review
            """.strip(),
        }

        return [
            RuntimeRolePromptProfile(
                role_key=role_key,
                role_label=self._role_label(role_key),
                prompt_template=template,
                control_mode="editable",
                detail=detail,
                variables=[],
            )
            for role_key, template in templates.items()
        ]

    def _council_prompt_defaults(self) -> list[RuntimeRolePromptProfile]:
        detail = "Editable council prompt template with live workspace placeholders."

        def _profile(role_key: str, template: str) -> RuntimeRolePromptProfile:
            return RuntimeRolePromptProfile(
                role_key=role_key,
                role_label=self._role_label(role_key),
                prompt_template=template.strip(),
                control_mode="editable",
                detail=detail,
                variables=[],
            )

        return [
            _profile(
                "trend_vol",
                """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт: {contract_code}; горизонт: {horizon}; сессия: {session_type}; торговый день: {trading_day}.
Рынок сейчас: цена {current_price}, изменение за день {price_change_pct}, workflow {workflow_state}, итог сигнала {signal_direction}, статус {signal_status}.
Тезис сигнала: {signal_summary}

Что поддерживает сценарий:
{why_now}

Что давит на сценарий:
{pushback}

Что отменяет сценарий:
{invalidation}

Твоя задача:
1. Оцени, есть ли на этом горизонте направленный режим или перед нами шум.
2. Отдели устойчивое движение от случайного выброса и скажи, насколько волатильность помогает или мешает сценарию.
3. Назови один главный риск слома тезиса и один признак, который сильнее всего укрепит доверие.

Жёсткие правила:
- Не выдумывай данные, которых нет во входе.
- Не давай команд на сделку, автоторговлю или order routing.
- Если данных недостаточно, прямо скажи об этом.

Ответ верни строго в блоках:
verdict: support | caution | oppose
regime:
why_now:
primary_risk:
what_changes_mind:
confidence_note:
                """,
            ),
            _profile(
                "flow_liquidity",
                """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт: {contract_code}; цена {current_price}; дневное изменение {price_change_pct}.
Источник цены: {price_source}; режим данных: {data_mode}; состояние справочника: {reference_status}; workflow: {workflow_state}.
Текущий тезис: {signal_summary}

Что поддерживает сценарий:
{why_now}

Что настораживает:
{pushback}

Твоя задача:
1. Оцени, выглядит ли движение подтверждённым потоком и ликвидностью или оно хрупкое.
2. Отдели чистое участие рынка от тонкого рынка, проскальзывания и искажённой реакции.
3. Скажи, что именно надо подтвердить, чтобы движению можно было доверять сильнее.

Жёсткие правила:
- Не подменяй отсутствие данных догадками.
- Не предлагай order routing и не описывай исполнение как готовую команду.
- Если качество потока нельзя оценить надёжно, пометь это явно.

Ответ верни строго в блоках:
verdict: support | caution | oppose
liquidity_state: clean | mixed | thin
trust_in_move:
execution_risk:
fragility_signal:
what_needs_confirmation:
                """,
            ),
            _profile(
                "oi_roll",
                """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; активный контракт {active_contract}; следующий контракт {next_contract}.
До экспирации {days_to_expiry} дней; доля ролла {roll_share}; состояние ролла {roll_state}; горизонт {horizon}.
Текущий итог сигнала: {signal_direction}; статус {signal_status}; workflow {workflow_state}.
Сводка сигнала: {signal_summary}

Что поддерживает сценарий:
{why_now}

Что может испортить чтение серии:
{pushback}

Что отменяет сценарий:
{invalidation}

Твоя задача:
1. Оцени, насколько текущий контракт и переход между контрактами загрязняют сигнал.
2. Отдельно проговори риск expiry pressure и риск неверного чтения OI/ролла.
3. Скажи, какое наблюдение уменьшит сомнение по серии сильнее всего.

Жёсткие правила:
- Не выдумывай OI, календарный спред или roll-метрики, которых нет во входе.
- Не своди анализ к общим словам, если риск связан с конкретной фазой ролла.
- Не давай торговых инструкций.

Ответ верни строго в блоках:
verdict: support | caution | oppose
roll_state_assessment: clean | transitional | contaminated
expiry_pressure: low | medium | high
contamination_risk:
break_point:
what_reduces_risk:
                """,
            ),
            _profile(
                "macro_event",
                """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; сессия {session_type}; торговый день {trading_day}; горизонт {horizon}.
Цена сейчас {current_price}; итог сигнала {signal_direction}; статус {signal_status}; workflow {workflow_state}.
Текущий тезис: {signal_summary}

Что поддерживает сценарий:
{why_now}

Что делает картину хрупкой:
{pushback}

Твоя задача:
1. Оцени, насколько ближайший макро- и событийный контекст совместим с текущим тезисом.
2. Скажи, что именно может быстро сломать идею даже при нормальной цене.
3. Назови один фактор, который снизит event risk и позволит доверять сценарию сильнее.

Жёсткие правила:
- Не придумывай конкретные события, если их нет во входе.
- Не подменяй оценку event risk общим рыночным фоном.
- Не давай торговых команд и не обещай результат.

Ответ верни строго в блоках:
verdict: support | caution | oppose
event_regime: clean | fragile | blocked
event_risk:
why_this_can_break:
what_derisks_it:
watch_next:
                """,
            ),
            _profile(
                "skeptic",
                """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт {contract_code}; горизонт {horizon}; workflow {workflow_state}.
Итог сигнала сейчас: {signal_direction}; статус {signal_status}; confidence {confidence_final}; skeptic_score {skeptic_score}.
Сводка сигнала: {signal_summary}

Что поддерживает сценарий:
{why_now}

Что уже вызывает сомнение:
{pushback}

Что отменяет сценарий:
{invalidation}

Твоя задача:
1. Сначала ищи сильнейший сценарий отказа, а не подтверждение идеи.
2. Найди структурную слабость тезиса, недостающее доказательство и место, где авторы могут обманываться шумом.
3. Если идея всё же выживает, коротко скажи, что именно её спасает.

Жёсткие правила:
- Не смягчай формулировки ради согласия с остальными участниками.
- Не повторяй вход как пересказ; выделяй только реальные уязвимости.
- Не давай order routing и не предлагай автоматическое действие.

Ответ верни строго в блоках:
skeptic_verdict: pass | soft_fail | reject | human_review
strongest_rejection_case:
weak_point:
missing_evidence:
what_would_rescue_setup:
bottom_line:
                """,
            ),
            _profile(
                "arbiter",
                """
Ты участник трейдерского совета IMOEX. Роль: {role_label}.
Инструмент: {root_code}; контракт {contract_code}; цена {current_price}; горизонт {horizon}; сессия {session_type}.
Текущее состояние: workflow {workflow_state}; итог сигнала {signal_direction}; статус {signal_status}; confidence {confidence_final}; skeptic_score {skeptic_score}.
Тезис сигнала: {signal_summary}

Что поддерживает сценарий:
{why_now}

Что ограничивает сценарий:
{pushback}

Что отменяет сценарий:
{invalidation}

Твоя задача:
1. Собери выводы совета в один понятный человеческий итог.
2. Разведи, что у идеи реально сильное, а что пока не даёт поднять уверенность.
3. Скажи, что именно пользователю стоит наблюдать следующим, прежде чем усиливать доверие к сценарию.

Жёсткие правила:
- Не выдумывай мнения участников, которых нет во входе.
- Не превращай итог в команду на сделку или автоторговлю.
- Если уверенность ограничена, это должно быть видно прямо в вердикте.

Ответ верни строго в блоках:
final_call: bullish | bearish | no_edge
confidence_band: low | medium | high
why_now:
what_blocks_conviction:
what_user_should_watch_next:
publication_verdict: publish | downrank | hold_for_review
                """,
            ),
        ]

    def _default_role_prompts(self) -> list[RuntimeRolePromptProfile]:
        detail = "Editable council prompt template with live workspace placeholders."
        return [
            RuntimeRolePromptProfile(
                role_key="trend_vol",
                role_label=self._role_label("trend_vol"),
                prompt_template=(
                    "Ты участник трейдерского совета IMOEX: {role_label}.\n"
                    "Root: {root_code}; контракт: {active_contract}; горизонт: {horizon}; сессия: {session_type}; день: {trading_day}.\n"
                    "Цена сейчас: {current_price} ({price_change_pct}); workflow: {workflow_state}; итог сигнала: {signal_direction} / {signal_status}.\n"
                    "Сводка: {signal_summary}\n"
                    "Драйверы:\n{why_now}\n"
                    "Сдерживающие факторы:\n{pushback}\n"
                    "Условия отмены:\n{invalidation}\n"
                    "Задача: оцени тренд, волатильность и устойчивость движения на этом горизонте. Ответ должен быть только decision support, без автоторговли."
                ),
                control_mode="editable",
                detail=detail,
                variables=[],
            ),
            RuntimeRolePromptProfile(
                role_key="flow_liquidity",
                role_label=self._role_label("flow_liquidity"),
                prompt_template=(
                    "Ты участник трейдерского совета IMOEX: {role_label}.\n"
                    "Инструмент: {root_code}; контракт: {active_contract}; цена: {current_price}; изменение за день: {price_change_pct}.\n"
                    "Источник цены: {price_source}; режим данных: {data_mode}; справочник: {reference_status}.\n"
                    "Текущий тезис: {signal_summary}\n"
                    "Драйверы:\n{why_now}\n"
                    "Риски:\n{pushback}\n"
                    "Задача: оцени качество потока, ликвидности и риск того, что движение искажено тонким рынком. Никакого order routing, только decision support."
                ),
                control_mode="editable",
                detail=detail,
                variables=[],
            ),
            RuntimeRolePromptProfile(
                role_key="oi_roll",
                role_label=self._role_label("oi_roll"),
                prompt_template=(
                    "Ты участник трейдерского совета IMOEX: {role_label}.\n"
                    "Активный контракт: {active_contract}; следующий: {next_contract}; дней до экспирации: {days_to_expiry}; доля ролла: {roll_share}.\n"
                    "Root: {root_code}; горизонт: {horizon}; текущий итог: {signal_direction}.\n"
                    "Сводка сигнала: {signal_summary}\n"
                    "Условия отмены:\n{invalidation}\n"
                    "Задача: оцени влияние ролла, перехода между контрактами и expiry pressure на надёжность сетапа."
                ),
                control_mode="editable",
                detail=detail,
                variables=[],
            ),
            RuntimeRolePromptProfile(
                role_key="macro_event",
                role_label=self._role_label("macro_event"),
                prompt_template=(
                    "Ты участник трейдерского совета IMOEX: {role_label}.\n"
                    "Root: {root_code}; сессия: {session_type}; торговый день: {trading_day}; горизонт: {horizon}.\n"
                    "Текущий тезис: {signal_summary}\n"
                    "Драйверы:\n{why_now}\n"
                    "Сдерживающие факторы:\n{pushback}\n"
                    "Задача: оцени event risk и вероятность того, что ближайший макро-контекст быстро сломает текущий тезис."
                ),
                control_mode="editable",
                detail=detail,
                variables=[],
            ),
            RuntimeRolePromptProfile(
                role_key="skeptic",
                role_label=self._role_label("skeptic"),
                prompt_template=(
                    "Ты участник трейдерского совета IMOEX: {role_label}.\n"
                    "Root: {root_code}; контракт: {active_contract}; горизонт: {horizon}; workflow: {workflow_state}.\n"
                    "Итог сигнала сейчас: {signal_direction} / {signal_status}; confidence: {confidence_final}; skeptic_score: {skeptic_score}.\n"
                    "Сводка: {signal_summary}\n"
                    "Драйверы:\n{why_now}\n"
                    "Риски и возражения:\n{pushback}\n"
                    "Условия отмены:\n{invalidation}\n"
                    "Задача: найти противоречия, слабые места тезиса и причины не брать идею. Не подтверждай сетап, если в нём есть структурная слабость."
                ),
                control_mode="editable",
                detail=detail,
                variables=[],
            ),
            RuntimeRolePromptProfile(
                role_key="arbiter",
                role_label=self._role_label("arbiter"),
                prompt_template=(
                    "Ты участник трейдерского совета IMOEX: {role_label}.\n"
                    "Root: {root_code}; контракт: {active_contract}; цена: {current_price}; горизонт: {horizon}; workflow: {workflow_state}.\n"
                    "Итог сигнала: {signal_direction} / {signal_status}; confidence: {confidence_final}; skeptic_score: {skeptic_score}.\n"
                    "Сводка: {signal_summary}\n"
                    "Драйверы:\n{why_now}\n"
                    "Что сдерживает:\n{pushback}\n"
                    "Что отменяет сценарий:\n{invalidation}\n"
                    "Задача: собрать выводы совета в один понятный итог для человека. Только decision support, никогда не предлагай автоторговлю."
                ),
                control_mode="editable",
                detail=detail,
                variables=[],
            ),
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

    def _extract_variables(self, template: str) -> list[str]:
        seen: set[str] = set()
        variables: list[str] = []
        for match in self.VARIABLE_PATTERN.finditer(template):
            variable = match.group(1)
            if variable in seen:
                continue
            seen.add(variable)
            variables.append(variable)
        return variables

    def _render_prompt(self, template: str, context: dict[str, object]) -> str:
        safe_context = _SafePromptContext(
            {
                key: str(value)
                for key, value in context.items()
            }
        )
        try:
            return template.format_map(safe_context)
        except (KeyError, ValueError):
            return template
