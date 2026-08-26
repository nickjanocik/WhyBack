"""Tests for WhyBack's quality scripts behavior."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

import scripts.run_quality_gate as quality_gate
from scripts.run_quality_gate import (
    GatePaths,
    ProcessResult,
    discover_eval_input,
    run_quality_gate,
    source_tree_hash,
    validate_test_outputs,
)
from scripts.verify_artifacts import sha256_file, verify_artifact_tree
from whyback import __version__
from whyback.agent.actions import ActionId, load_action_catalog
from whyback.agent.prompts import PROMPT_HASH, PROMPT_VERSION
from whyback.config import SOURCE_COMMIT, SOURCE_REPOSITORY
from whyback.data.download import SOURCE_FILES
from whyback.data.manifest import DataManifest, preparation_code_sha256
from whyback.observability import AuditEvent, AuditEventName
from whyback.observability.audit import read_audit_events
from whyback.reporting import (
    build_interpretation_limits,
    build_population_context,
    render_report_html,
    render_report_markdown,
    render_trace_html,
)
from whyback.reporting.models import ReportData
from whyback.tools.contracts import (
    EvidenceRecord,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)

RUN_ID = UUID("00000000-0000-4000-8000-000000000077")


def _write_gate_project(root: Path) -> None:
    """Write gate project for this test."""

    (root / "src" / "whyback").mkdir(parents=True)
    (root / "src" / "whyback" / "__init__.py").write_text("\n", encoding="utf-8")
    (root / "configs").mkdir()
    (root / "configs" / "app.toml").write_text(
        """
[data]
source_repository = "official/example"
source_commit = "abc123"
[agent]
default_model = "test-model"
default_thinking_level = "medium"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        """
[tool.coverage.report]
fail_under = 85
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    eval_input = root / "artifacts" / "demo" / "evals" / "normalized_runs.json"
    eval_input.parent.mkdir(parents=True)
    eval_input.write_text('{"runs": []}\n', encoding="utf-8")


def test_model_metadata_requires_a_non_space_gemini_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that model metadata requires a non space gemini key."""

    _write_gate_project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "  \t")

    blank = quality_gate.model_metadata(tmp_path)

    assert blank["gemini_api_key_present"] is False
    assert blank["live_execution_permitted"] is False

    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")

    present = quality_gate.model_metadata(tmp_path)

    assert present["gemini_api_key_present"] is True
    assert present["live_execution_permitted"] is True


def _report() -> dict[str, object]:
    """Create a strict report document for artifact-verification tests."""

    population_context = build_population_context(())
    interpretation_limits = build_interpretation_limits(
        (), population_context.context_classification
    )
    return {
        "schema_version": 2,
        "product_name": "WhyBack",
        "tagline": "Find the why. Choose the way back.",
        "investigator_name": "WhyBack Investigator",
        "provenance": {
            "dataset_kind": "synthetic",
            "dataset_source_repository": "whyback/tests",
            "dataset_source_commit": "whyback-test-fixture-v1",
            "source_hashes": {"fixture": "c" * 64},
            "backend": "scripted",
            "execution_mode": "scripted_control",
            "model": "scripted/whyback-v1",
            "application_version": __version__,
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": PROMPT_HASH,
            "generated_at": "2026-01-01T00:00:02Z",
            "timing_mode": "actual_utc_and_monotonic",
        },
        "run_id": str(RUN_ID),
        "household_id": "77",
        "run_status": "failed",
        "decline": {
            "evidence_id": f"detector_{RUN_ID}",
            "run_id": str(RUN_ID),
            "household_id": "77",
            "source": "decline_detector",
            "baseline_start_week": 38,
            "baseline_end_week": 45,
            "recent_start_week": 46,
            "recent_end_week": 53,
            "baseline_retailer_sales_value": 100.0,
            "recent_retailer_sales_value": 50.0,
            "baseline_distinct_baskets": 8,
            "recent_distinct_baskets": 4,
            "baseline_active_weeks": 8,
            "recent_active_weeks": 4,
            "sales_drop": 0.5,
            "trip_drop": 0.5,
            "active_week_drop": 0.5,
            "decline_score": 0.5,
            "eligible": True,
            "flagged": True,
            "partial_week_limitation": "Week 53 may be partial.",
        },
        "population_context": population_context.model_dump(mode="json"),
        "investigation_path": [],
        "likely_drivers": [],
        "supporting_evidence": [],
        "counterevidence": [],
        "evidence_ledger": [],
        "alternative_explanations": [],
        "uncertainties": [],
        "interpretation_limits": interpretation_limits.model_dump(mode="json"),
        "action": None,
        "limitations": [
            "Week 53 may be partial.",
            "The fixture intentionally records a failed run.",
        ],
        "tool_warnings": [],
        "verification_issues": ["The fixture intentionally records a failed run."],
        "failure_reason": "The fixture intentionally records a failed run.",
        "human_review_required": True,
    }


def _detector_snapshot() -> dict[str, object]:
    """Create a detector snapshot for artifact-verification tests."""

    decline = _report()["decline"]
    assert isinstance(decline, dict)
    return {
        key: value
        for key, value in decline.items()
        if key not in {"evidence_id", "run_id", "source"}
    }


def _write_trace(path: Path, *, model: str = "scripted/whyback-v1") -> None:
    """Write trace for this test."""

    started = datetime(2026, 1, 1, tzinfo=UTC)
    events = (
        AuditEvent(
            timestamp=started,
            event=AuditEventName.RUN_STARTED,
            run_id=RUN_ID,
            household_id="77",
            details={
                "model": model,
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": PROMPT_HASH,
                "dataset_kind": "synthetic",
                "dataset_source_repository": "whyback/tests",
                "dataset_source_commit": "whyback-test-fixture-v1",
                "application_version": __version__,
                "timing_mode": "actual_utc_and_monotonic",
                "decline_score": 0.5,
                "detector_snapshot": _detector_snapshot(),
                "remaining_tool_budget": 5,
                "remaining_turn_budget": 6,
            },
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=1),
            event=AuditEventName.RUN_COMPLETED,
            run_id=RUN_ID,
            household_id="77",
            details={
                "status": "failed",
                "message": "The fixture intentionally records a failed run.",
            },
        ),
    )
    path.write_text(
        "".join(f"{event.model_dump_json()}\n" for event in events),
        encoding="utf-8",
    )


def _write_exact_report_bundle(report_path: Path, value: dict[str, object]) -> None:
    """Write exact report bundle for this test."""

    report = ReportData.model_validate(value)
    report_path.write_text(
        f"{json.dumps(report.model_dump(mode='json'), indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    report_path.with_suffix(".md").write_text(
        render_report_markdown(report), encoding="utf-8"
    )
    report_path.with_suffix(".html").write_text(
        render_report_html(report), encoding="utf-8"
    )


def _write_exact_trace_view(trace_path: Path) -> None:
    """Write exact trace view for this test."""

    trace_path.with_suffix(".html").write_text(
        render_trace_html(read_audit_events(trace_path)), encoding="utf-8"
    )


def _rehash_manifest(root: Path, manifest_name: str = "artifact_manifest.json") -> None:
    """Recompute hashes for manifest for this test."""

    manifest_path = root / manifest_name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _write_results_files(root: Path) -> None:
    """Write results files for this test."""

    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    terminal = set(manifest["completed_household_ids"]) | set(
        manifest["failed_household_ids"]
    )
    reports = [
        json.loads(
            (root / f"customer_{household_id}" / "report.json").read_text(
                encoding="utf-8"
            )
        )
        for household_id in manifest["selected_household_ids"]
        if household_id in terminal
    ]
    (root / "results.json").write_text(
        f"{json.dumps(reports, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    label = (
        "synthetic fixture"
        if manifest["dataset_kind"] == "synthetic"
        else "official full Complete Journey"
    )
    backend = manifest["backend"]
    note = (
        "Scripted runs are deterministic orchestration controls and are not "
        "presented as live model judgments. All displayed metrics were computed "
        "by the deterministic detector or registered analytical tools."
        if backend == "scripted"
        else (
            "These runs used the configured Gemini function-calling backend."
            if backend == "gemini" and reports
            else "No live model call was attempted because GEMINI_API_KEY was absent."
            if backend == "gemini"
            else "These runs used the configured OpenAI Responses backend."
            if reports
            else "No live model call was attempted because OPENAI_API_KEY was absent."
        )
    )
    rows = [
        f"| {report['household_id']} | {report['decline']['decline_score']:.3f} "
        f"| {report['run_status']} | "
        f"{report['action']['action_id'] if report['action'] else 'UNAVAILABLE'} |"
        for report in reports
    ]
    (root / "RESULTS.md").write_text(
        "\n".join(
            [
                "# WhyBack demo results",
                "",
                "### Find the why. Choose the way back.",
                "",
                f"Dataset: **{label}**. Backend: **{backend}**.",
                "",
                note,
                "",
                "| Household | Decline score | Status | Human-reviewed action |",
                "|---|---:|---|---|",
                *rows,
                "",
                "The decline score is a transparent heuristic, not a churn "
                "probability.",
                "Every action is a recommendation requiring human review; no outreach "
                "was executed.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_valid_artifacts(root: Path) -> None:
    """Write valid artifacts for this test."""

    run_dir = root / "customer_77"
    run_dir.mkdir(parents=True)
    report_path = run_dir / "report.json"
    trace_path = run_dir / "trace.jsonl"
    _write_exact_report_bundle(report_path, _report())
    _write_trace(trace_path)
    _write_exact_trace_view(trace_path)
    manifest = {
        "schema_version": 1,
        "product_name": "WhyBack",
        "dataset_kind": "synthetic",
        "dataset_source_repository": "whyback/tests",
        "dataset_source_commit": "whyback-test-fixture-v1",
        "backend": "scripted",
        "execution_mode": "scripted",
        "selected_household_ids": ["77"],
        "completed_household_ids": [],
        "failed_household_ids": ["77"],
        "skipped_household_ids": [],
        "files": {},
    }
    (root / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "live_status.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "skipped",
                "execution_mode": "skipped",
                "reason": "GEMINI_API_KEY was absent.",
            }
        ),
        encoding="utf-8",
    )
    _write_results_files(root)
    _rehash_manifest(root)


def _write_standalone_artifacts(root: Path) -> None:
    """Write standalone artifacts for this test."""

    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "report.json"
    trace_path = root / "trace.jsonl"
    _write_exact_report_bundle(report_path, _report())
    _write_trace(trace_path)
    _write_exact_trace_view(trace_path)
    manifest = {
        "schema_version": 1,
        "product": "WhyBack",
        "artifact_profile": "standalone_run",
        "dataset_kind": "synthetic",
        "dataset_source_repository": "whyback/tests",
        "dataset_source_commit": "whyback-test-fixture-v1",
        "source_manifest": None,
        "backend": "scripted",
        "execution_mode": "scripted",
        "model_execution": "scripted_control",
        "timing_mode": "actual_utc_and_monotonic",
        "selected_household_ids": ["77"],
        "completed_household_ids": [],
        "failed_household_ids": ["77"],
        "skipped_household_ids": [],
        "human_review_required": True,
        "customer_outreach_executed": False,
        "files": {},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _rehash_manifest(root, "manifest.json")


def _write_audit_events(path: Path, events: tuple[AuditEvent, ...]) -> None:
    """Write audit events for this test."""

    path.write_text(
        "".join(f"{event.model_dump_json()}\n" for event in events),
        encoding="utf-8",
    )
    _write_exact_trace_view(path)


def _write_evidence_artifacts(root: Path) -> None:
    """Write evidence artifacts for this test."""

    _write_valid_artifacts(root)
    source_hashes = {"transactions": "b" * 64}
    query_hash = "a" * 64
    call_id = "call-0000000000-01-customer_trend"
    evidence = EvidenceRecord(
        evidence_id=f"ev_{call_id}_001",
        run_id=RUN_ID,
        household_id="77",
        source_tool=ToolName.CUSTOMER_TREND,
        source_tool_call_id=call_id,
        metric="distinct_trips",
        baseline_value=8.0,
        recent_value=4.0,
        change=-4.0,
        unit="count",
        query_hash=query_hash,
    )
    result = ToolResult(
        tool_call_id=call_id,
        tool_name=ToolName.CUSTOMER_TREND,
        status=ToolStatus.OK,
        evidence=(evidence,),
        provenance=ToolProvenance(
            dataset_source_commit="whyback-test-fixture-v1",
            source_hashes=source_hashes,
            normalized_parameters={"household_id": "77"},
            query_hash=query_hash,
            rows_examined=12,
            elapsed_ms=2.5,
            application_version=__version__,
        ),
    )
    report = _report()
    provenance = report["provenance"]
    assert isinstance(provenance, dict)
    provenance["source_hashes"] = source_hashes
    provenance["generated_at"] = "2026-01-01T00:00:09Z"
    report_evidence = {
        **evidence.model_dump(mode="json"),
        "role": "context",
        "source_status": "ok",
    }
    report["evidence_ledger"] = [report_evidence]
    report["investigation_path"] = [
        {
            "decision_number": 1,
            "tool_name": "customer_trend",
            "tool_label": "Customer trend",
            "investigation_question": "Inspect recorded visit cadence.",
            "final_status": "ok",
            "attempt_count": 1,
            "retry_count": 0,
            "total_latency_ms": 2.5,
            "evidence_ids": [evidence.evidence_id],
            "limitations": [],
        }
    ]
    _write_exact_report_bundle(root / "customer_77" / "report.json", report)

    started = datetime(2026, 1, 1, tzinfo=UTC)
    common = {"run_id": RUN_ID, "household_id": "77"}
    events = (
        AuditEvent(
            timestamp=started,
            event=AuditEventName.RUN_STARTED,
            details={
                "model": "scripted/whyback-v1",
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": PROMPT_HASH,
                "dataset_kind": "synthetic",
                "dataset_source_repository": "whyback/tests",
                "dataset_source_commit": "whyback-test-fixture-v1",
                "application_version": __version__,
                "timing_mode": "actual_utc_and_monotonic",
                "decline_score": 0.5,
                "detector_snapshot": _detector_snapshot(),
                "remaining_tool_budget": 2,
                "remaining_turn_budget": 2,
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=1),
            event=AuditEventName.MODEL_DECISION_REQUESTED,
            details={"remaining_tool_budget": 2, "remaining_turn_budget": 2},
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=2),
            event=AuditEventName.MODEL_DECISION_RECEIVED,
            details={
                "provider_call_id": "scripted-001",
                "model": "scripted/whyback-v1",
                "decision_kind": "tool",
                "selected_tool": "customer_trend",
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=3),
            event=AuditEventName.TOOL_REQUESTED,
            details={
                "tool_name": "customer_trend",
                "investigation_question": "Inspect recorded visit cadence.",
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=4),
            event=AuditEventName.TOOL_STARTED,
            details={
                "tool_name": "customer_trend",
                "tool_call_id": call_id,
                "attempt": 1,
                "remaining_tool_budget": 2,
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=5),
            event=AuditEventName.TOOL_COMPLETED,
            details={
                "tool_name": "customer_trend",
                "tool_call_id": call_id,
                "attempt": 1,
                "status": "ok",
                "retryable": False,
                "latency_ms": 2.5,
                "rows_examined": 12,
                "query_hash": query_hash,
                "evidence_ids": [evidence.evidence_id],
                "limitations": [],
                "diagnostics": {},
                "tool_result": result.model_dump(mode="json"),
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=6),
            event=AuditEventName.EVIDENCE_ADDED,
            details={
                "evidence_id": evidence.evidence_id,
                "source_tool": "customer_trend",
                "source_tool_call_id": call_id,
                "metric": "distinct_trips",
                "limitations": [],
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=7),
            event=AuditEventName.MODEL_DECISION_REQUESTED,
            details={"remaining_tool_budget": 1, "remaining_turn_budget": 1},
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=8),
            event=AuditEventName.RUN_COMPLETED,
            details={
                "status": "failed",
                "message": "The fixture intentionally records a failed run.",
            },
            **common,
        ),
    )
    _write_audit_events(root / "customer_77" / "trace.jsonl", events)
    _write_results_files(root)
    _rehash_manifest(root)


def _write_live_artifacts(root: Path) -> None:
    """Write live artifacts for this test."""

    _write_valid_artifacts(root)
    report = _report()
    provenance = report["provenance"]
    assert isinstance(provenance, dict)
    provenance.update(
        {
            "backend": "gemini",
            "execution_mode": "live_gemini",
            "model": "gemini-3.7-flash",
            "generated_at": "2026-01-01T00:00:07Z",
        }
    )
    report["run_status"] = "insufficient_evidence"
    report["failure_reason"] = None
    report["verification_issues"] = []
    report["alternative_explanations"] = [
        "Recorded evidence does not distinguish the observed signal from unobserved "
        "activity outside this retailer."
    ]
    report["uncertainties"] = [
        "Customer intent and activity outside the recorded retailer data are not "
        "observed."
    ]
    report["limitations"] = [
        "Week 53 may be partial.",
        "Eligible-population and behavioral-peer context was not available; missing "
        "context must not be interpreted as neutral movement.",
        "Customer intent and activity outside the recorded retailer data are not "
        "observed.",
    ]
    action = load_action_catalog().get(ActionId.INSUFFICIENT_EVIDENCE)
    report["action"] = {
        "action_id": "INSUFFICIENT_EVIDENCE",
        "description": action.description,
        "rationale": "Available verified evidence does not support a customer action.",
        "resolved_confidence": "insufficient",
        "confidence_cap_applied": True,
        "confidence_adjustments": [
            {
                "context_classification": "insufficient_context",
                "maximum_confidence": "medium",
                "reason": (
                    "Population or peer context is insufficient, so missing comparison "
                    "evidence cannot be treated as neutral."
                ),
                "evidence_ids": [],
            }
        ],
        "recommended_success_metric": action.success_metric.description,
        "suggested_experiment": action.experiment.description,
        "human_review_required": True,
    }
    _write_exact_report_bundle(root / "customer_77" / "report.json", report)

    started = datetime(2026, 1, 1, tzinfo=UTC)
    common = {"run_id": RUN_ID, "household_id": "77"}
    events = (
        AuditEvent(
            timestamp=started,
            event=AuditEventName.RUN_STARTED,
            details={
                "model": "gemini-3.7-flash",
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": PROMPT_HASH,
                "dataset_kind": "synthetic",
                "dataset_source_repository": "whyback/tests",
                "dataset_source_commit": "whyback-test-fixture-v1",
                "application_version": __version__,
                "timing_mode": "actual_utc_and_monotonic",
                "decline_score": 0.5,
                "detector_snapshot": _detector_snapshot(),
                "remaining_tool_budget": 5,
                "remaining_turn_budget": 6,
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=1),
            event=AuditEventName.MODEL_DECISION_REQUESTED,
            details={"remaining_tool_budget": 5, "remaining_turn_budget": 6},
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=2),
            event=AuditEventName.MODEL_DECISION_RECEIVED,
            details={
                "provider_call_id": "gemini-function-call-fixture-1",
                "model": "gemini-3.7-flash",
                "decision_kind": "finish",
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=3),
            event=AuditEventName.FINISH_REQUESTED,
            details={
                "next_best_action_id": "INSUFFICIENT_EVIDENCE",
                "proposed_confidence": "low",
                "supporting_evidence_ids": [],
                "counterevidence_ids": [],
                "driver_claim_types": [],
                "driver_supporting_evidence_ids": [],
                "driver_counterevidence_ids": [],
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=4),
            event=AuditEventName.VERIFICATION_STARTED,
            details={"referenced_evidence_count": 0},
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=5),
            event=AuditEventName.VERIFICATION_PASSED,
            details={
                "next_best_action_id": "INSUFFICIENT_EVIDENCE",
                "resolved_confidence": "insufficient",
                "confidence_cap_applied": True,
                "confidence_adjustments": [
                    {
                        "context_classification": "insufficient_context",
                        "maximum_confidence": "medium",
                        "reason": (
                            "Population or peer context is insufficient, so missing "
                            "comparison evidence cannot be treated as neutral."
                        ),
                        "evidence_ids": [],
                    }
                ],
                "supporting_evidence_ids": [],
                "counterevidence_ids": [],
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=6),
            event=AuditEventName.RUN_COMPLETED,
            details={
                "status": "insufficient_evidence",
                "next_best_action_id": "INSUFFICIENT_EVIDENCE",
                "human_review_required": True,
            },
            **common,
        ),
    )
    _write_audit_events(root / "customer_77" / "trace.jsonl", events)
    manifest_path = root / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "backend": "gemini",
            "execution_mode": "live",
            "completed_household_ids": ["77"],
            "failed_household_ids": [],
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _write_results_files(root)
    _rehash_manifest(root)


def _write_failed_live_artifacts(root: Path) -> None:
    """Write a live request that failed before receiving a provider response."""

    _write_valid_artifacts(root)
    report_path = root / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["provenance"].update(
        {
            "backend": "gemini",
            "execution_mode": "live_gemini",
            "model": "gemini-3.7-flash",
        }
    )
    _write_exact_report_bundle(report_path, report)

    started = datetime(2026, 1, 1, tzinfo=UTC)
    common = {"run_id": RUN_ID, "household_id": "77"}
    events = (
        AuditEvent(
            timestamp=started,
            event=AuditEventName.RUN_STARTED,
            details={
                "model": "gemini-3.7-flash",
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": PROMPT_HASH,
                "dataset_kind": "synthetic",
                "dataset_source_repository": "whyback/tests",
                "dataset_source_commit": "whyback-test-fixture-v1",
                "application_version": __version__,
                "timing_mode": "actual_utc_and_monotonic",
                "decline_score": 0.5,
                "detector_snapshot": _detector_snapshot(),
                "remaining_tool_budget": 5,
                "remaining_turn_budget": 6,
            },
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=1),
            event=AuditEventName.MODEL_DECISION_REQUESTED,
            details={"remaining_tool_budget": 5, "remaining_turn_budget": 6},
            **common,
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=2),
            event=AuditEventName.RUN_COMPLETED,
            details={
                "status": "failed",
                "failure_type": "ModelBackendError",
                "message": "The fixture intentionally records a failed run.",
            },
            **common,
        ),
    )
    _write_audit_events(root / "customer_77" / "trace.jsonl", events)
    manifest_path = root / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({"backend": "gemini", "execution_mode": "live"})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _write_results_files(root)
    _rehash_manifest(root)


def _write_official_provenance_artifacts(root: Path) -> None:
    """Write official provenance artifacts for this test."""

    _write_valid_artifacts(root)
    data_manifest = DataManifest(
        preparation_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        preparation_code_sha256=preparation_code_sha256(),
        source_tree_version="fixture-source-tree",
        source_tree_dirty=False,
        sources=tuple(
            {
                "filename": source.name,
                "sha256": source.sha256,
                "size_bytes": source.size_bytes,
                "row_count": 0,
                "schema_summary": {},
                "missing_values": {},
            }
            for source in SOURCE_FILES
        ),
        prepared=(),
        diagnostics={},
    )
    canonical_manifest = (
        json.dumps(data_manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    )
    manifest_hash = hashlib.sha256(canonical_manifest.encode()).hexdigest()
    source_hashes = {
        "manifest/manifest.json": manifest_hash,
        **{f"source/{item.name}": item.sha256 for item in SOURCE_FILES},
    }
    data_provenance = {
        "schema_version": 1,
        "dataset_kind": "official_complete_journey",
        "manifest_sha256": manifest_hash,
        "manifest": data_manifest.model_dump(mode="json"),
    }
    (root / "data_provenance.json").write_text(
        f"{json.dumps(data_provenance, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )

    report_path = root / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["provenance"].update(
        {
            "dataset_kind": "official_complete_journey",
            "dataset_source_repository": SOURCE_REPOSITORY,
            "dataset_source_commit": SOURCE_COMMIT,
            "source_hashes": source_hashes,
        }
    )
    _write_exact_report_bundle(report_path, report)
    trace_path = root / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["details"].update(
        {
            "dataset_kind": "official_complete_journey",
            "dataset_source_repository": SOURCE_REPOSITORY,
            "dataset_source_commit": SOURCE_COMMIT,
        }
    )
    _rewrite_trace_rows(trace_path, rows)
    manifest_path = root / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "dataset_kind": "official_complete_journey",
            "dataset_source_repository": SOURCE_REPOSITORY,
            "dataset_source_commit": SOURCE_COMMIT,
            "source_manifest": "data_provenance.json",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _write_results_files(root)
    _rehash_manifest(root)


def _rewrite_trace_rows(trace_path: Path, rows: list[dict[str, object]]) -> None:
    """Rewrite trace rows for this test."""

    trace_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    _write_exact_trace_view(trace_path)


def test_source_tree_hash_is_stable_and_excludes_generated_artifacts(
    tmp_path: Path,
) -> None:
    """Verify that source tree hash is stable and excludes generated artifacts."""

    _write_gate_project(tmp_path)
    first = source_tree_hash(tmp_path)
    generated = tmp_path / "artifacts" / "tests"
    generated.mkdir(parents=True)
    (generated / "test_audit.json").write_text("changed", encoding="utf-8")
    assert source_tree_hash(tmp_path) == first

    (tmp_path / "src" / "whyback" / "__init__.py").write_text(
        "VERSION = 1\n", encoding="utf-8"
    )
    source_change = source_tree_hash(tmp_path)
    assert source_change != first

    web = tmp_path / "web"
    web.mkdir()
    (web / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
    web_change = source_tree_hash(tmp_path)
    assert web_change != source_change

    dependencies = web / "node_modules" / "example"
    dependencies.mkdir(parents=True)
    (dependencies / "index.js").write_text("generated\n", encoding="utf-8")
    assert source_tree_hash(tmp_path) == web_change

    (tmp_path / ".gitleaksignore").write_text(
        "reviewed-fingerprint\n", encoding="utf-8"
    )
    assert source_tree_hash(tmp_path) != web_change


def test_test_output_validation_requires_branch_coverage_and_threshold(
    tmp_path: Path,
) -> None:
    """Verify that test output validation requires branch coverage and threshold."""

    paths = GatePaths.under(tmp_path)
    paths.directory.mkdir(parents=True)
    paths.junit_xml.write_text(
        '<testsuites><testsuite tests="7" failures="0" errors="0" '
        'skipped="0" time="0.5" /></testsuites>\n',
        encoding="utf-8",
    )
    paths.coverage_json.write_text(
        json.dumps({"totals": {"percent_covered": 91.25, "num_branches": 80}}),
        encoding="utf-8",
    )
    assert validate_test_outputs(paths, 85.0)[0]

    paths.coverage_json.write_text(
        json.dumps({"totals": {"percent_covered": 84.99, "num_branches": 80}}),
        encoding="utf-8",
    )
    passed, message = validate_test_outputs(paths, 85.0)
    assert not passed
    assert "below the configured" in message


def test_eval_discovery_uses_only_the_conventional_normalized_fixture(
    tmp_path: Path,
) -> None:
    """Verify that eval discovery uses only the conventional normalized fixture."""

    (tmp_path / "artifacts" / "demo" / "evals").mkdir(parents=True)
    unrelated = tmp_path / "artifacts" / "demo" / "evaluation_report.json"
    unrelated.write_text("{}\n", encoding="utf-8")
    assert discover_eval_input(tmp_path) is None

    expected = tmp_path / "artifacts" / "demo" / "evals" / "normalized_runs.json"
    expected.write_text('{"runs": []}\n', encoding="utf-8")
    assert discover_eval_input(tmp_path) == expected


def test_artifact_verifier_accepts_hashed_scripted_bundle_and_explicit_skip(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify a hashed scripted bundle with an explicit live skip."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _write_valid_artifacts(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed
    assert result.execution_modes == ("scripted", "skipped")
    assert "customer_77/report.json" in result.checked_files


def test_artifact_verifier_accepts_strict_standalone_run_profile(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier accepts strict standalone run profile."""

    _write_standalone_artifacts(tmp_path)

    result = verify_artifact_tree(tmp_path)

    assert result.passed, result.issues
    assert result.execution_modes == ("scripted",)


def test_artifact_verifier_allows_the_server_verification_seal(tmp_path: Path) -> None:
    """Verify that artifact verifier allows the server verification seal."""

    _write_valid_artifacts(tmp_path)
    (tmp_path / ".whyback-live-verification.json").write_text(
        '{"status":"verified_live_gemini"}\n', encoding="utf-8"
    )

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed, result.issues


def test_artifact_verifier_reconciles_complete_detector_and_failure_reason(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier reconciles complete detector and failure reason."""

    _write_valid_artifacts(tmp_path)
    report_path = tmp_path / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["decline"]["baseline_retailer_sales_value"] = 999.0
    report["failure_reason"] = None
    _write_exact_report_bundle(report_path, report)
    _write_results_files(tmp_path)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {item.code for item in result.issues}
    assert "report_detector_mismatch" in codes
    assert "report_failure_reason_mismatch" in codes


def test_artifact_verifier_fails_closed_for_tampering_and_malformed_trace(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify that artifact verifier fails closed for tampering and malformed trace."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _write_valid_artifacts(tmp_path)
    (tmp_path / "customer_77" / "report.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "customer_77" / "trace.jsonl").write_text(
        "not-json\n", encoding="utf-8"
    )

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {issue.code for issue in result.issues}

    assert not result.passed
    assert "malformed_report" in codes
    assert "malformed_trace" in codes
    assert "file_hash_mismatch" in codes


def test_artifact_verifier_rejects_live_label_backed_by_scripted_trace(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify that artifact verifier rejects live label backed by scripted trace."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _write_valid_artifacts(tmp_path)
    manifest_path = tmp_path / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution_mode"] = "live"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {issue.code for issue in result.issues}

    assert "live_label_mismatch" in codes
    assert "manifest_trace_mode_mismatch" in codes


def test_artifact_verifier_accepts_honest_skip_only_tree_with_explicit_flag(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify an honest skip-only tree when the caller permits it."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    status_path = tmp_path / "live_model_status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "skipped_no_api_key",
                "execution_mode": "skipped",
                "reason": "GEMINI_API_KEY was absent.",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_mode": "skipped",
                "reason": "GEMINI_API_KEY was absent.",
                "files": {status_path.name: sha256_file(status_path)},
            }
        ),
        encoding="utf-8",
    )

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed
    assert result.execution_modes == ("skipped",)


def test_artifact_verifier_reconstructs_report_evidence_from_tool_results(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier reconstructs report evidence from tool results."""

    _write_evidence_artifacts(tmp_path)
    initial = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    assert initial.passed, initial.issues

    report_path = tmp_path / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["evidence_ledger"][0]["recent_value"] = 3.0
    _write_exact_report_bundle(report_path, report)
    _write_results_files(tmp_path)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    assert "report_ledger_mismatch" in {item.code for item in result.issues}


def test_artifact_verifier_validates_strict_tool_result_and_attempt_budget(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier validates strict tool result and attempt budget."""

    _write_evidence_artifacts(tmp_path)
    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    completed = next(row for row in rows if row["event"] == "tool_completed")
    completed["details"]["tool_result"]["unexpected"] = True
    started = next(row for row in rows if row["event"] == "tool_started")
    started["details"]["remaining_tool_budget"] = 99
    _rewrite_trace_rows(trace_path, rows)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {item.code for item in result.issues}
    assert "malformed_tool_result" in codes
    assert "trace_budget_invalid" in codes


def test_artifact_verifier_exactly_rerenders_and_rejects_unhashed_extras(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier exactly rerenders and rejects unhashed extras."""

    _write_valid_artifacts(tmp_path)
    markdown = tmp_path / "customer_77" / "report.md"
    markdown.write_text(
        "tampered but still branded WhyBack human review\n", encoding="utf-8"
    )
    _rehash_manifest(tmp_path)
    (tmp_path / "customer_77" / "unreviewed.txt").write_text(
        "not declared\n", encoding="utf-8"
    )

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {item.code for item in result.issues}
    assert "report_render_mismatch" in codes
    assert "unhashed_artifact_file" in codes


def test_artifact_verifier_rejects_symlinks_even_when_hashed(tmp_path: Path) -> None:
    """Verify that artifact verifier rejects symlinks even when hashed."""

    _write_valid_artifacts(tmp_path)
    link = tmp_path / "customer_77" / "report-link.json"
    link.symlink_to("report.json")
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert "artifact_symlink_forbidden" in {item.code for item in result.issues}


def test_artifact_verifier_reconciles_results_json_and_markdown(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier reconciles results json and markdown."""

    _write_valid_artifacts(tmp_path)
    (tmp_path / "results.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / "RESULTS.md").write_text("stale summary\n", encoding="utf-8")
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {item.code for item in result.issues}
    assert "results_index_mismatch" in codes
    assert "results_markdown_mismatch" in codes


def test_artifact_verifier_rejects_stale_customer_directories_and_duplicate_ids(
    tmp_path: Path,
) -> None:
    """Verify rejection of stale directories and duplicate customer IDs."""

    _write_valid_artifacts(tmp_path)
    shutil.copytree(tmp_path / "customer_77", tmp_path / "customer_88")
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {item.code for item in result.issues}
    assert "manifest_artifact_directory_mismatch" in codes
    assert "duplicate_report_run_id" in codes
    assert "duplicate_trace_run_id" in codes


def test_artifact_verifier_rejects_orphan_report(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier rejects orphan report."""

    _write_valid_artifacts(tmp_path)
    (tmp_path / "customer_77" / "trace.jsonl").unlink()
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    assert "orphan_report" in {item.code for item in result.issues}


def test_completed_trace_requires_passing_verdict_and_matching_confidence(
    tmp_path: Path,
) -> None:
    """Verify that completed trace requires passing verdict and matching confidence."""

    _write_live_artifacts(tmp_path)
    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if '"event":"verification_passed"' not in line
    ]
    _rewrite_trace_rows(trace_path, rows)
    _rehash_manifest(tmp_path)

    no_verdict = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    assert "trace_terminal_verdict_mismatch" in {
        item.code for item in no_verdict.issues
    }

    confidence_root = tmp_path / "confidence"
    _write_live_artifacts(confidence_root)
    report_path = confidence_root / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["action"]["confidence_cap_applied"] = False
    _write_exact_report_bundle(report_path, report)
    _write_results_files(confidence_root)
    _rehash_manifest(confidence_root)
    bad_confidence = verify_artifact_tree(confidence_root, allow_live_skipped=True)
    assert "report_verdict_mismatch" in {item.code for item in bad_confidence.issues}


def test_artifact_verifier_reconciles_context_confidence_adjustments(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier reconciles context confidence adjustments."""

    _write_live_artifacts(tmp_path)
    report_path = tmp_path / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["action"]["confidence_adjustments"][0]["reason"] = (
        "A tampered confidence-adjustment reason."
    )
    with pytest.raises(
        ValidationError,
        match="Confidence adjustments do not match deterministic evidence policy",
    ):
        _write_exact_report_bundle(report_path, report)


def test_artifact_verifier_recomputes_coordinated_confidence_tampering(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier recomputes coordinated confidence tampering."""

    _write_live_artifacts(tmp_path)
    report_path = tmp_path / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["action"]["confidence_cap_applied"] = False
    _write_exact_report_bundle(report_path, report)

    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    for row in rows:
        if row["event"] == AuditEventName.VERIFICATION_PASSED.value:
            row["details"]["confidence_cap_applied"] = False
    _rewrite_trace_rows(trace_path, rows)
    _write_results_files(tmp_path)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    issue_codes = {item.code for item in result.issues}
    assert "report_verdict_mismatch" not in issue_codes
    assert "report_deterministic_confidence_mismatch" in issue_codes
    assert "trace_deterministic_confidence_mismatch" in issue_codes


def test_artifact_verifier_reconstructs_methodology_sections_from_trace(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier reconstructs methodology sections from trace."""

    context_root = tmp_path / "context"
    _write_live_artifacts(context_root)
    context_report_path = context_root / "customer_77" / "report.json"
    context_report = json.loads(context_report_path.read_text(encoding="utf-8"))
    context_report["population_context"]["limitations"] = [
        "A schema-valid but unevidenced population limitation."
    ]
    _write_exact_report_bundle(context_report_path, context_report)
    _write_results_files(context_root)
    _rehash_manifest(context_root)

    context_result = verify_artifact_tree(context_root, allow_live_skipped=True)
    assert "report_population_context_mismatch" in {
        item.code for item in context_result.issues
    }

    limits_root = tmp_path / "limits"
    _write_live_artifacts(limits_root)
    limits_report_path = limits_root / "customer_77" / "report.json"
    limits_report = json.loads(limits_report_path.read_text(encoding="utf-8"))
    limits_report["interpretation_limits"]["causal_limitations"][0] = (
        "Reduced promotions caused the household's decline."
    )
    _write_exact_report_bundle(limits_report_path, limits_report)
    _write_results_files(limits_root)
    _rehash_manifest(limits_root)

    limits_result = verify_artifact_tree(limits_root, allow_live_skipped=True)
    limits_codes = {item.code for item in limits_result.issues}
    assert "report_interpretation_limits_mismatch" in limits_codes
    assert "unsafe_report_prose" in limits_codes


def test_artifact_verifier_rejects_coordinated_public_issue_tampering(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier rejects coordinated public issue tampering."""

    _write_live_artifacts(tmp_path)
    report_path = tmp_path / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    unsafe = "Reduced promotions caused the decline by 42%."
    report["limitations"].append(unsafe)
    report["verification_issues"].append(unsafe)
    _write_exact_report_bundle(report_path, report)
    _write_results_files(tmp_path)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    codes = {item.code for item in result.issues}
    assert "report_limitation_mismatch" in codes
    assert "report_verification_issue_mismatch" in codes
    assert "unsafe_report_prose" in codes


def test_artifact_verifier_rejects_unsafe_model_prose_in_rendered_trace(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier rejects unsafe model prose in rendered trace."""

    _write_live_artifacts(tmp_path)
    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    decision = next(
        row
        for row in rows
        if row["event"] == AuditEventName.MODEL_DECISION_RECEIVED.value
    )
    decision["details"]["decision_summary"] = (
        "Reduced promotions caused the decline by 42%."
    )
    _rewrite_trace_rows(trace_path, rows)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert "unsafe_trace_prose" in {item.code for item in result.issues}


def test_live_history_and_skip_are_credential_independent(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify that live history and skip are credential independent."""

    _write_live_artifacts(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    without_current_key = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder-not-a-real-key")
    with_current_key = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert without_current_key.passed, without_current_key.issues
    assert with_current_key.passed, with_current_key.issues
    assert with_current_key.execution_modes == ("live", "skipped")


def test_artifact_verifier_accepts_live_backend_failure_before_response(
    tmp_path: Path,
) -> None:
    """Accept an unanswered live request with one sanitized backend failure."""

    _write_failed_live_artifacts(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed, result.issues
    assert result.execution_modes == ("live", "skipped")


@pytest.mark.parametrize("provider_id", [None, "", "scripted-001"])
def test_artifact_verifier_keeps_provider_id_required_for_completed_live_run(
    tmp_path: Path,
    provider_id: str | None,
) -> None:
    """Reject completed live decisions without a genuine provider response ID."""

    _write_live_artifacts(tmp_path)
    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    received = next(row for row in rows if row["event"] == "model_decision_received")
    if provider_id is None:
        del received["details"]["provider_call_id"]
    else:
        received["details"]["provider_call_id"] = provider_id
    _rewrite_trace_rows(trace_path, rows)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert "unsubstantiated_live_trace" in {item.code for item in result.issues}


@pytest.mark.parametrize(
    "tampering",
    ["missing_request", "wrong_failure_type", "decision_claim", "evidence_claim"],
)
def test_artifact_verifier_rejects_unsubstantiated_live_failure_exception(
    tmp_path: Path,
    tampering: str,
) -> None:
    """Reject a no-response exception unless its failure lifecycle is exact."""

    _write_failed_live_artifacts(tmp_path)
    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    if tampering == "missing_request":
        rows.pop(1)
    elif tampering == "wrong_failure_type":
        rows[-1]["details"]["failure_type"] = "ToolExecutionError"
    elif tampering == "decision_claim":
        rows[-1]["details"]["decision_summary"] = "A model decision was available."
    else:
        evidence_claim = {
            **rows[1],
            "event": "evidence_added",
            "details": {
                "evidence_id": "unsupported-evidence",
                "source_tool": "customer_trend",
                "source_tool_call_id": "unsupported-call",
                "metric": "distinct_trips",
                "limitations": [],
            },
        }
        rows.insert(-1, evidence_claim)
    _rewrite_trace_rows(trace_path, rows)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert "unsubstantiated_live_trace" in {item.code for item in result.issues}


def test_artifact_verifier_preserves_legacy_openai_live_provenance(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier preserves legacy openai live provenance."""

    _write_live_artifacts(tmp_path)
    report_path = tmp_path / "customer_77" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["provenance"].update(
        {
            "backend": "openai",
            "execution_mode": "live_openai",
            "model": "gpt-5.6-sol",
        }
    )
    _write_exact_report_bundle(report_path, report)

    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["details"]["model"] = "gpt-5.6-sol"
    received = next(row for row in rows if row["event"] == "model_decision_received")
    received["details"].update(
        {"provider_call_id": "resp_fixture_1", "model": "gpt-5.6-sol"}
    )
    _rewrite_trace_rows(trace_path, rows)

    manifest_path = tmp_path / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["backend"] = "openai"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _write_results_files(tmp_path)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed, result.issues
    assert result.execution_modes == ("live", "skipped")


def test_artifact_verifier_rejects_provider_id_from_the_wrong_backend(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier rejects provider id from the wrong backend."""

    _write_live_artifacts(tmp_path)
    trace_path = tmp_path / "customer_77" / "trace.jsonl"
    rows = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    received = next(row for row in rows if row["event"] == "model_decision_received")
    received["details"]["provider_call_id"] = "resp_wrong_provider"
    _rewrite_trace_rows(trace_path, rows)
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert "report_trace_provider_mismatch" in {issue.code for issue in result.issues}


def test_artifact_verifier_reconciles_embedded_official_data_provenance(
    tmp_path: Path,
) -> None:
    """Verify that artifact verifier reconciles embedded official data provenance."""

    _write_official_provenance_artifacts(tmp_path)
    initial = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    assert initial.passed, initial.issues

    provenance_path = tmp_path / "data_provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["manifest_sha256"] = "0" * 64
    provenance_path.write_text(
        f"{json.dumps(provenance, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    _rehash_manifest(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert "source_manifest_hash_mismatch" in {item.code for item in result.issues}


class FakeRunner:
    """Test double that provides FakeRunner behavior."""

    def __init__(self, *, fail_sync: bool = False) -> None:
        """Initialize this test double with its controlled behavior."""

        self.fail_sync = fail_sync
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: tuple[str, ...], cwd: Path) -> ProcessResult:
        """Run the fake command and return its configured result."""

        self.commands.append(command)
        if command == ("git", "rev-parse", "HEAD"):
            return ProcessResult(0, "deadbeef\n", "")
        if command == ("git", "branch", "--show-current"):
            return ProcessResult(0, "codex/test\n", "")
        if command[:2] == ("git", "status"):
            return ProcessResult(0, "", "")
        if command == ("uv", "--version"):
            return ProcessResult(0, "uv 1.2.3\n", "")
        if command[:2] == ("uv", "sync") and self.fail_sync:
            return ProcessResult(2, "sync began\n", "lock mismatch\n")
        if "pytest" in command:
            paths = GatePaths.under(cwd)
            paths.directory.mkdir(parents=True, exist_ok=True)
            paths.junit_xml.write_text(
                '<testsuites><testsuite tests="7" failures="0" errors="0" '
                'skipped="0" time="0.5" /></testsuites>\n',
                encoding="utf-8",
            )
            paths.coverage_json.write_text(
                json.dumps({"totals": {"percent_covered": 90.0, "num_branches": 20}}),
                encoding="utf-8",
            )
        return ProcessResult(0, f"ran {' '.join(command)}\n", "")


def test_quality_gate_parser_allows_skip_by_default_and_can_require_live() -> None:
    """Verify that quality gate parser allows skip by default and can require live."""

    parser = quality_gate._parser()

    assert parser.parse_args([]).allow_live_skipped is True
    assert parser.parse_args(["--allow-live-skipped"]).allow_live_skipped is True
    assert parser.parse_args(["--require-live"]).allow_live_skipped is False


def test_quality_gate_retains_preliminary_failure_and_runs_later_steps(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify that quality gate retains preliminary failure and runs later steps."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _write_gate_project(tmp_path)
    runner = FakeRunner(fail_sync=True)
    fixed_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    ticks = iter(float(value) for value in range(100))

    exit_code, audit = run_quality_gate(
        tmp_path,
        allow_live_skipped=True,
        runner=runner,
        now=lambda: fixed_time,
        monotonic=lambda: next(ticks),
    )

    assert exit_code == 1
    assert audit["failure_observations"] == ["frozen_sync"]
    steps = {item["name"]: item for item in audit["steps"]}
    assert steps["frozen_sync"]["stdout"] == "sync began\n"
    assert steps["frozen_sync"]["stderr"] == "lock mismatch\n"
    assert steps["artifact_verification"]["status"] == "passed"
    assert steps["deterministic_evals"]["status"] == "passed"
    assert audit["test_summary"]["junit"]["tests"] == 7
    assert len(audit["invocations"]) == 1
    assert GatePaths.under(tmp_path).audit_json.is_file()
    assert GatePaths.under(tmp_path).audit_markdown.is_file()
    assert ("uv", "run", "pyright") in runner.commands
    assert ("npm", "--prefix", "web", "ci", "--ignore-scripts") in runner.commands
    assert ("npm", "--prefix", "web", "run", "check") in runner.commands

    second_exit, second_audit = run_quality_gate(
        tmp_path,
        allow_live_skipped=True,
        runner=FakeRunner(),
        now=lambda: fixed_time,
        monotonic=lambda: next(ticks),
    )
    assert second_exit == 0
    invocations = second_audit["invocations"]
    assert len(invocations) == 2
    assert invocations[0]["failure_observations"] == ["frozen_sync"]
    assert invocations[1]["passed"] is True


def test_quality_gate_fails_when_required_eval_input_is_missing(
    tmp_path: Path,
) -> None:
    """Verify that quality gate fails when required eval input is missing."""

    _write_gate_project(tmp_path)
    (tmp_path / "artifacts" / "demo" / "evals" / "normalized_runs.json").unlink()
    fixed_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    ticks = iter(float(value) for value in range(100))

    exit_code, audit = run_quality_gate(
        tmp_path,
        allow_live_skipped=True,
        runner=FakeRunner(),
        now=lambda: fixed_time,
        monotonic=lambda: next(ticks),
    )

    steps = {item["name"]: item for item in audit["steps"]}
    assert exit_code == 1
    assert steps["deterministic_evals"]["status"] == "failed"
    assert audit["passed"] is False


def test_quality_gate_checkpoints_never_claim_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that quality gate checkpoints never claim completion."""

    _write_gate_project(tmp_path)
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        quality_gate,
        "_persist_audit",
        lambda _paths, audit: captured.append(dict(audit)),
    )
    fixed_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    ticks = iter(float(value) for value in range(100))

    exit_code, final = run_quality_gate(
        tmp_path,
        allow_live_skipped=True,
        runner=FakeRunner(),
        now=lambda: fixed_time,
        monotonic=lambda: next(ticks),
    )

    assert exit_code == 0
    assert captured[-1]["lifecycle"] == "completed"
    assert captured[-1]["passed"] is True
    assert all(
        checkpoint["passed"] is False
        for checkpoint in captured[:-1]
        if checkpoint["lifecycle"] == "running"
    )
    assert final["required_steps_complete"] is True


def test_quality_gate_clears_stale_per_invocation_outputs(tmp_path: Path) -> None:
    """Verify that quality gate clears stale per invocation outputs."""

    _write_gate_project(tmp_path)
    paths = GatePaths.under(tmp_path)
    paths.directory.mkdir(parents=True, exist_ok=True)
    for path in (
        paths.junit_xml,
        paths.coverage_json,
        paths.artifact_verification_json,
        paths.live_gemini_artifact_verification_json,
        paths.official_artifact_verification_json,
        paths.official_type_a_artifact_verification_json,
        paths.eval_json,
        paths.eval_markdown,
    ):
        path.write_text("stale-secret-marker", encoding="utf-8")
    fixed_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    ticks = iter(float(value) for value in range(100))

    run_quality_gate(
        tmp_path,
        allow_live_skipped=True,
        runner=FakeRunner(),
        now=lambda: fixed_time,
        monotonic=lambda: next(ticks),
    )

    assert "stale-secret-marker" not in paths.junit_xml.read_text(encoding="utf-8")
    assert "stale-secret-marker" not in paths.coverage_json.read_text(encoding="utf-8")
    assert not paths.artifact_verification_json.exists()
    assert not paths.live_gemini_artifact_verification_json.exists()
    assert not paths.eval_json.exists()


def test_malformed_prior_audit_retains_only_error_and_digest(tmp_path: Path) -> None:
    """Verify that malformed prior audit retains only error and digest."""

    _write_gate_project(tmp_path)
    paths = GatePaths.under(tmp_path)
    paths.directory.mkdir(parents=True, exist_ok=True)
    secret = "".join(("sk-", "1234567890abcdefghijklmnop"))
    paths.audit_json.write_text(f"not-json {secret}", encoding="utf-8")
    fixed_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    ticks = iter(float(value) for value in range(100))

    exit_code, audit = run_quality_gate(
        tmp_path,
        allow_live_skipped=True,
        runner=FakeRunner(),
        now=lambda: fixed_time,
        monotonic=lambda: next(ticks),
    )

    retained = audit["environment"]["unreadable_prior_audit"]
    assert exit_code == 1
    assert "sha256" in retained and "error" in retained
    assert "raw_content" not in retained
    assert secret not in json.dumps(audit)
