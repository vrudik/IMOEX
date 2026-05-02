from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_private_beta_evidence.ps1"
CANDIDATE_WRAPPER = REPO_ROOT / "scripts" / "private_beta_candidate_check.ps1"
REQUIRED_BROWSER_CHECKS = [
    "workspace_opened",
    "workspace_morning_brief_visible",
    "runtime_admin_key_save_clear",
    "runtime_prompt_diff",
    "runtime_prompt_draft_saved",
    "runtime_prompt_draft_dismissed",
    "workspace_root_switch",
    "market_fixture_current_price_visible",
    "market_fixture_day_week_month_charts_visible",
    "market_fixture_chart_measurement",
    "market_fixture_multi_root_switch",
    "market_fixture_mobile_charts_visible",
    "market_fixture_mobile_no_horizontal_overflow",
]
REQUIRED_PERFORMANCE_LABELS = [
    "api_dashboard",
    "api_workspace",
    "page_workspace",
    "api_signal_detail",
    "page_signal_detail",
    "page_runtime",
    "page_council",
    "api_journal",
    "page_journal",
    "api_product_readiness",
]


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _write_json(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _artifact(tmp_path: Path, key: str, *, present: bool = True, content: str | None = None) -> dict[str, object]:
    artifact_path = tmp_path / f"{key}.txt"
    if content is None:
        content = f"{key} evidence"
    if present:
        artifact_path.write_text(content, encoding="utf-8")
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "path": str(artifact_path),
        "present": present,
        "copied_to": "",
        "required_evidence": f"{key} required evidence",
    }


def _manifest(
    tmp_path: Path,
    *,
    missing: list[str] | None = None,
    candidate_revision: str = "test",
    release_authorized: bool = False,
    browser_checks: list[str] | None = None,
    release_notes_content: str | None = None,
) -> Path:
    missing = missing or []
    browser_checks = REQUIRED_BROWSER_CHECKS if browser_checks is None else browser_checks
    release_notes_content = release_notes_content or "\n".join(
        [
            "# Private-Beta Release Notes",
            "Candidate: test",
            "This release-note record does not authorize production deployment.",
            "The app remains signals-only decision support.",
            "## Candidate Summary",
            "- Analytics mode: disabled",
            "- Telegram mode: disabled",
            "- Market-data mode: degraded",
            "## Evidence Links",
            "- Workspace snapshot JSON: C:/tmp/workspace-snapshot.json",
            "- Telegram preview JSON: C:/tmp/telegram-preview.json",
            "- Telegram ops preview JSON: C:/tmp/telegram-ops-preview.json",
            "## Accepted Warnings",
            "- None",
            "## Explicit Non-Goals",
            "## Support Boundary Confirmation",
            "- Candidate understands this is decision support only: yes",
            "- Candidate accepts support boundaries before walkthrough: yes",
            "- Candidate understands market-data truthfulness policy: yes",
            "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
            "## Operator Walkthrough Result",
            "- Workspace trust ribbon checked: pass",
            "- Morning Command Brief checked: pass",
            "- Current price and day/week/month charts checked: pass",
            "- Root switch checked: pass",
            "- Signal detail checked: pass",
            "- Council prompts checked: pass",
            "- Runtime prompt diff/dismiss/restore checked: pass",
            "- Journal tags and filters checked: pass",
            "- Delivery reason trails checked: pass",
            "- Telegram preview/dry-run checked: pass",
            "- Backup/restore evidence checked: pass",
            "## Rollback Record",
            "- Rollback owner: operator",
            "- Previous application revision: previous-test-revision",
            "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
            "- Stop command or process owner: local operator",
            "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
            "## Decision",
            "- Private-beta candidate accepted: deferred",
            "- Decision owner: operator",
            "- Decision timestamp: 2026-04-28T00:00:00Z",
        ]
    )
    artifacts = [
        _artifact(
            tmp_path,
            "release_check",
            content="[release-check] product readiness OK\n[release-check] OK\n",
        ),
        {
            **_artifact(tmp_path, "browser_smoke"),
            "path": _write_json(tmp_path / "browser_smoke.json", {"checks": browser_checks}),
        },
        {
            **_artifact(tmp_path, "product_readiness"),
            "path": _write_json(tmp_path / "product_readiness.json", {"release_gate": "pass"}),
        },
        {
            **_artifact(tmp_path, "admin_health"),
            "path": _write_json(tmp_path / "admin_health.json", {"status": "ok"}),
        },
        {
            **_artifact(tmp_path, "workspace_snapshot"),
            "path": _write_json(
                tmp_path / "workspace_snapshot.json",
                {
                    "morning_brief": {
                        "signals_only": True,
                        "market_status": "degraded",
                        "top_attention": [{"title": "Review Si", "href": "/workspace"}],
                        "dont_chase": [],
                        "telegram_status": "preview",
                    }
                },
            ),
        },
        {
            **_artifact(tmp_path, "telegram_preview"),
            "path": _write_json(
                tmp_path / "telegram_preview.json",
                {
                    "root": "Si",
                    "configured": False,
                    "event_kind": "digest",
                    "delivery_allowed": True,
                    "message": "IMOEX Signal Brief",
                },
            ),
        },
        {
            **_artifact(tmp_path, "telegram_ops_preview"),
            "path": _write_json(
                tmp_path / "telegram_ops_preview.json",
                {
                    "enabled": False,
                    "configured": False,
                    "alert_items": [
                        {
                            "kind": "scheduler_failed_runs",
                            "severity": "warning",
                            "title": "Scheduler failed runs",
                            "detail": "No failed runs in fixture.",
                        }
                    ],
                    "message": "IMOEX Ops Alerts",
                },
            ),
        },
        {
            **_artifact(tmp_path, "restore_drill"),
            "path": _write_json(
                tmp_path / "restore_drill.json",
                {"release_gate": "pass", "integrity_check": "ok", "roots": 1, "final_signals": 1},
            ),
        },
        {
            **_artifact(tmp_path, "performance_baseline"),
            "path": _write_json(
                tmp_path / "performance_baseline.json",
                {"results": [{"label": label} for label in REQUIRED_PERFORMANCE_LABELS]},
            ),
        },
        _artifact(tmp_path, "alerting_expectations"),
        _artifact(tmp_path, "analytics_catalog"),
        _artifact(tmp_path, "sales_readiness"),
        _artifact(
            tmp_path,
            "acceptance_checklist",
            content=(
                "# Private-Beta Acceptance Checklist\n"
                "## Candidate Output Prefill\n"
                "This prefill does not authorize private beta, production deployment, pricing, "
                "broker execution, order routing, or autotrading.\n"
            ),
        ),
        _artifact(tmp_path, "release_notes_template"),
        {
            **_artifact(tmp_path, "release_notes"),
            "path": _write_text(
                tmp_path / "release_notes.md",
                release_notes_content,
            ),
        },
    ]
    for artifact in artifacts:
        if artifact["key"] in missing:
            artifact["present"] = False
            artifact["path"] = str(tmp_path / f"missing-{artifact['key']}.txt")

    manifest_path = tmp_path / "private-beta-evidence-manifest.json"
    _write_json(
        manifest_path,
        {
            "generated_at": "2026-04-28T00:00:00Z",
            "candidate_revision": candidate_revision,
            "analytics_mode": "disabled",
            "signals_only_decision_support": True,
            "release_decision_authorized": release_authorized,
            "production_deployment_authorized": False,
            "pricing_commitment_authorized": False,
            "order_routing_authorized": False,
            "missing_required_artifacts": missing,
            "artifacts": artifacts,
        },
    )
    return manifest_path


def _run_validator(manifest: Path, output: Path, *, allow_draft: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(VALIDATOR),
        "-ManifestPath",
        str(manifest),
        "-OutputPath",
        str(output),
    ]
    if allow_draft:
        command.append("-AllowDraft")
    return subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def _run_candidate_wrapper(output_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(CANDIDATE_WRAPPER),
        "-OutputDir",
        str(output_dir),
        *args,
    ]
    return subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def test_private_beta_evidence_validator_passes_complete_manifest(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    output = tmp_path / "validation.json"

    result = _run_validator(manifest, output)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["failures"] == []
    assert payload["warnings"] == []


def test_private_beta_candidate_wrapper_blocks_full_run_without_prepared_release_notes(tmp_path: Path) -> None:
    result = _run_candidate_wrapper(tmp_path / "candidate")

    combined_output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "Full private-beta candidate generation requires completed release notes" in combined_output
    assert "[private-beta-candidate] running release check" not in combined_output


def test_private_beta_evidence_validator_allows_draft_missing_artifacts(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, missing=["browser_smoke", "restore_drill"])
    output = tmp_path / "validation-draft.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert [item["code"] for item in payload["warnings"]] == ["draft_missing_artifacts"]


def test_private_beta_evidence_validator_blocks_unknown_candidate_revision(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, candidate_revision="unknown")
    output = tmp_path / "validation-unknown-revision.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "candidate_revision_unknown" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_unknown_candidate_revision(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, candidate_revision="unknown")
    output = tmp_path / "validation-draft-unknown-revision.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_candidate_revision_unknown" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_release_notes_candidate_revision_mismatch(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, candidate_revision="abc123")
    output = tmp_path / "validation-revision-mismatch.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_candidate_revision_mismatch" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_release_notes_candidate_revision_mismatch(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path, candidate_revision="abc123")
    output = tmp_path / "validation-draft-revision-mismatch.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_candidate_revision_mismatch" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_release_notes_analytics_mode_mismatch(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Analytics mode: disabled", "- Analytics mode: local-only-export"),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-analytics-mode-mismatch.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_analytics_mode_mismatch" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_release_notes_analytics_mode_mismatch(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Analytics mode: disabled", "- Analytics mode: local-only-export"),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-draft-analytics-mode-mismatch.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_analytics_mode_mismatch" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_incomplete_telegram_preview(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "telegram_preview":
            Path(artifact["path"]).write_text(
                json.dumps({"root": "", "event_kind": "auto-send", "message": ""}),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-telegram-preview-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failure_codes = {item["code"] for item in payload["failures"]}
    assert "telegram_preview_root_missing" in failure_codes
    assert "telegram_preview_event_kind_invalid" in failure_codes
    assert "telegram_preview_delivery_allowed_missing" in failure_codes
    assert "telegram_preview_configured_missing" in failure_codes
    assert "telegram_preview_message_missing" in failure_codes


def test_private_beta_evidence_validator_blocks_incomplete_workspace_morning_brief(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "workspace_snapshot":
            Path(artifact["path"]).write_text(
                json.dumps(
                    {
                        "morning_brief": {
                            "signals_only": False,
                            "market_status": "synthetic",
                            "telegram_status": "auto-send",
                        },
                        "broker_execution_enabled": True,
                    }
                ),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-workspace-morning-brief-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failure_codes = {item["code"] for item in payload["failures"]}
    assert "workspace_snapshot_morning_brief_not_signals_only" in failure_codes
    assert "workspace_snapshot_morning_brief_market_status_invalid" in failure_codes
    assert "workspace_snapshot_morning_brief_attention_missing" in failure_codes
    assert "workspace_snapshot_morning_brief_dont_chase_missing" in failure_codes
    assert "workspace_snapshot_morning_brief_telegram_status_invalid" in failure_codes
    assert "workspace_snapshot_forbidden_execution_flag" in failure_codes


def test_private_beta_evidence_validator_blocks_incomplete_telegram_ops_preview(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "telegram_ops_preview":
            Path(artifact["path"]).write_text(json.dumps({"message": ""}), encoding="utf-8")
            break
    output = tmp_path / "validation-telegram-ops-preview-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failure_codes = {item["code"] for item in payload["failures"]}
    assert "telegram_ops_preview_enabled_missing" in failure_codes
    assert "telegram_ops_preview_configured_missing" in failure_codes
    assert "telegram_ops_preview_alert_items_missing" in failure_codes
    assert "telegram_ops_preview_message_missing" in failure_codes


def test_private_beta_evidence_validator_blocks_incomplete_telegram_ops_preview_alert_item(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "telegram_ops_preview":
            Path(artifact["path"]).write_text(
                json.dumps(
                    {
                        "enabled": False,
                        "configured": False,
                        "alert_items": [{"kind": "scheduler_failed_runs"}],
                        "message": "IMOEX Ops Alerts",
                    }
                ),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-telegram-ops-preview-item-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "telegram_ops_preview_alert_item_incomplete" for item in payload["failures"])


def test_private_beta_evidence_validator_blocks_missing_acceptance_prefill(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in payload["artifacts"]:
        if artifact["key"] == "acceptance_checklist":
            Path(artifact["path"]).write_text("# Private-Beta Acceptance Checklist\n", encoding="utf-8")
            break
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    output = tmp_path / "validation-acceptance-prefill-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failure_codes = {item["code"] for item in payload["failures"]}
    assert "acceptance_checklist_prefill_missing" in failure_codes
    assert "acceptance_checklist_safety_phrase_missing" in failure_codes


def test_private_beta_evidence_validator_warns_on_draft_missing_acceptance_prefill(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in payload["artifacts"]:
        if artifact["key"] == "acceptance_checklist":
            Path(artifact["path"]).write_text("# Private-Beta Acceptance Checklist\n", encoding="utf-8")
            break
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    output = tmp_path / "validation-draft-acceptance-prefill-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    warning_codes = {item["code"] for item in payload["warnings"]}
    assert "draft_acceptance_checklist_prefill_missing" in warning_codes
    assert "draft_acceptance_checklist_safety_phrase_missing" in warning_codes


def test_private_beta_evidence_validator_blocks_release_notes_placeholders(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes Template",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "## Rollback Record",
                "## Decision",
                "- Private-beta candidate accepted: <yes/no/deferred>",
                "- Decision owner: <owner>",
            ]
        ),
    )
    output = tmp_path / "validation-release-notes-placeholders-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_placeholders_present" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_release_notes_placeholders(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes Template",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "## Rollback Record",
                "## Decision",
                "- Private-beta candidate accepted: <yes/no/deferred>",
                "- Decision owner: <owner>",
            ]
        ),
    )
    output = tmp_path / "validation-draft-release-notes-placeholders-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_placeholders_present" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_unconfirmed_support_boundaries(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: no",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Rollback Record",
            ]
        ),
    )
    output = tmp_path / "validation-support-boundary-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_support_boundary_unconfirmed" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_unconfirmed_support_boundaries(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: no",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Rollback Record",
            ]
        ),
    )
    output = tmp_path / "validation-draft-support-boundary-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(
        item["code"] == "draft_release_notes_support_boundary_unconfirmed"
        for item in payload["warnings"]
    )


def test_private_beta_evidence_validator_blocks_incomplete_walkthrough_result(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: fail",
                "- Root switch checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-walkthrough-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_walkthrough_check_not_pass" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_incomplete_walkthrough_result(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: not run",
                "- Root switch checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-draft-walkthrough-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(
        item["code"] == "draft_release_notes_walkthrough_check_not_pass"
        for item in payload["warnings"]
    )


def test_private_beta_evidence_validator_blocks_incomplete_decision_record(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Rollback Record",
                "## Decision",
                "- Private-beta candidate accepted: maybe",
                "- Decision owner: TBD",
                "- Decision timestamp: tomorrow",
            ]
        ),
    )
    output = tmp_path / "validation-decision-record-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failure_codes = {item["code"] for item in payload["failures"]}
    assert "release_notes_decision_status_missing" in failure_codes
    assert "release_notes_decision_owner_missing" in failure_codes
    assert "release_notes_decision_timestamp_missing" in failure_codes


def test_private_beta_evidence_validator_warns_on_draft_incomplete_decision_record(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Rollback Record",
                "## Decision",
                "- Private-beta candidate accepted: maybe",
                "- Decision owner: unknown",
                "- Decision timestamp: tomorrow",
            ]
        ),
    )
    output = tmp_path / "validation-draft-decision-record-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    warning_codes = {item["code"] for item in payload["warnings"]}
    assert "draft_release_notes_decision_status_missing" in warning_codes
    assert "draft_release_notes_decision_owner_missing" in warning_codes
    assert "draft_release_notes_decision_timestamp_missing" in warning_codes


def test_private_beta_evidence_validator_blocks_draft_candidate_acceptance(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: yes",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-draft-acceptance-failed.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "draft_release_notes_accepts_candidate" for item in payload["failures"])


def test_private_beta_evidence_validator_blocks_missing_accepted_warnings_decision(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Accepted Warnings",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-accepted-warnings-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_accepted_warnings_missing" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_missing_accepted_warnings_decision(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Accepted Warnings",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-draft-accepted-warnings-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_accepted_warnings_missing" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_incomplete_accepted_warning_detail(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Accepted Warnings",
                "- degraded feed during walkthrough, operator, review by 2026-05-01",
                "- vague warning without owner",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-accepted-warning-detail-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(
        item["code"] == "release_notes_accepted_warning_detail_incomplete"
        for item in payload["failures"]
    )


def test_private_beta_evidence_validator_warns_on_draft_incomplete_accepted_warning_detail(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Accepted Warnings",
                "- degraded feed during walkthrough, operator, review by 2026-05-01",
                "- vague warning without owner",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-draft-accepted-warning-detail-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(
        item["code"] == "draft_release_notes_accepted_warning_detail_incomplete"
        for item in payload["warnings"]
    )


def test_private_beta_evidence_validator_blocks_invalid_market_data_mode(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Candidate Summary",
                "- Market-data mode: synthetic",
                "## Accepted Warnings",
                "- None",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-market-data-mode-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_market_data_mode_invalid" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_invalid_market_data_mode(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Candidate Summary",
                "- Market-data mode: synthetic",
                "## Accepted Warnings",
                "- None",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Operator Walkthrough Result",
                "- Workspace trust ribbon checked: pass",
                "- Current price and day/week/month charts checked: pass",
                "- Root switch checked: pass",
                "- Signal detail checked: pass",
                "- Council prompts checked: pass",
                "- Runtime prompt diff/dismiss/restore checked: pass",
                "- Journal tags and filters checked: pass",
                "- Delivery reason trails checked: pass",
                "- Telegram preview/dry-run checked: pass",
                "- Backup/restore evidence checked: pass",
                "## Rollback Record",
                "- Rollback owner: operator",
                "- Previous application revision: previous-test-revision",
                "- Backup or restore artifact: C:/tmp/restore-drill-summary.json",
                "- Stop command or process owner: local operator",
                "- Verification after rollback: product-readiness, admin health, local smoke, Telegram preview/dry-run",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-draft-market-data-mode-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_market_data_mode_invalid" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_invalid_telegram_mode(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Telegram mode: disabled", "- Telegram mode: auto-send"),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-telegram-mode-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_telegram_mode_invalid" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_invalid_telegram_mode(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Telegram mode: disabled", "- Telegram mode: auto-send"),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-draft-telegram-mode-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_telegram_mode_invalid" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_missing_telegram_evidence_links(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Telegram preview JSON: C:/tmp/telegram-preview.json\n", "").replace(
                    "- Telegram ops preview JSON: C:/tmp/telegram-ops-preview.json\n",
                    "",
                ),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-telegram-evidence-links-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failures = [item for item in payload["failures"] if item["code"] == "release_notes_telegram_evidence_link_missing"]
    assert len(failures) == 2


def test_private_beta_evidence_validator_warns_on_draft_missing_telegram_evidence_links(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Telegram preview JSON: C:/tmp/telegram-preview.json\n", "").replace(
                    "- Telegram ops preview JSON: C:/tmp/telegram-ops-preview.json\n",
                    "",
                ),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-draft-telegram-evidence-links-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    warnings = [
        item for item in payload["warnings"] if item["code"] == "draft_release_notes_telegram_evidence_link_missing"
    ]
    assert len(warnings) == 2


def test_private_beta_evidence_validator_blocks_missing_workspace_evidence_link(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Workspace snapshot JSON: C:/tmp/workspace-snapshot.json\n", ""),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-workspace-evidence-link-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "release_notes_workspace_evidence_link_missing" for item in payload["failures"])


def test_private_beta_evidence_validator_warns_on_draft_missing_workspace_evidence_link(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    for artifact in manifest_payload["artifacts"]:
        if artifact["key"] == "release_notes":
            release_notes_path = Path(artifact["path"])
            release_notes = release_notes_path.read_text(encoding="utf-8")
            release_notes_path.write_text(
                release_notes.replace("- Workspace snapshot JSON: C:/tmp/workspace-snapshot.json\n", ""),
                encoding="utf-8",
            )
            break
    output = tmp_path / "validation-draft-workspace-evidence-link-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert any(item["code"] == "draft_release_notes_workspace_evidence_link_missing" for item in payload["warnings"])


def test_private_beta_evidence_validator_blocks_incomplete_rollback_record(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Rollback Record",
                "- Rollback owner: TBD",
                "- Previous application revision: unknown",
                "- Backup or restore artifact: none",
                "- Stop command or process owner: n/a",
                "- Verification after rollback: product-readiness",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-rollback-record-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    failure_codes = {item["code"] for item in payload["failures"]}
    assert "release_notes_rollback_owner_missing" in failure_codes
    assert "release_notes_rollback_revision_missing" in failure_codes
    assert "release_notes_rollback_artifact_missing" in failure_codes
    assert "release_notes_rollback_stop_owner_missing" in failure_codes
    assert "release_notes_rollback_verification_missing" in failure_codes


def test_private_beta_evidence_validator_warns_on_draft_incomplete_rollback_record(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        release_notes_content="\n".join(
            [
                "# Private-Beta Release Notes",
                "This release-note record does not authorize production deployment.",
                "The app remains signals-only decision support.",
                "## Explicit Non-Goals",
                "## Support Boundary Confirmation",
                "- Candidate understands this is decision support only: yes",
                "- Candidate accepts support boundaries before walkthrough: yes",
                "- Candidate understands market-data truthfulness policy: yes",
                "- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: yes",
                "## Rollback Record",
                "- Rollback owner: TBD",
                "- Previous application revision: unknown",
                "- Backup or restore artifact: none",
                "- Stop command or process owner: n/a",
                "- Verification after rollback: product-readiness",
                "## Decision",
                "- Private-beta candidate accepted: deferred",
                "- Decision owner: operator",
                "- Decision timestamp: 2026-04-28T00:00:00Z",
            ]
        ),
    )
    output = tmp_path / "validation-draft-rollback-record-warning.json"

    result = _run_validator(manifest, output, allow_draft=True)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    warning_codes = {item["code"] for item in payload["warnings"]}
    assert "draft_release_notes_rollback_owner_missing" in warning_codes
    assert "draft_release_notes_rollback_revision_missing" in warning_codes
    assert "draft_release_notes_rollback_artifact_missing" in warning_codes
    assert "draft_release_notes_rollback_stop_owner_missing" in warning_codes
    assert "draft_release_notes_rollback_verification_missing" in warning_codes


def test_private_beta_evidence_validator_blocks_launch_authorization_flag(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, release_authorized=True)
    output = tmp_path / "validation-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "invalid_flag" for item in payload["failures"])


def test_private_beta_evidence_validator_blocks_incomplete_browser_smoke(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, browser_checks=["workspace_opened"])
    output = tmp_path / "validation-browser-failed.json"

    result = _run_validator(manifest, output)

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any(item["code"] == "browser_smoke_missing_check" for item in payload["failures"])
