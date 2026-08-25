from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from scripts.run_quality_gate import (
    GatePaths,
    ProcessResult,
    discover_eval_input,
    run_quality_gate,
    source_tree_hash,
    validate_test_outputs,
)
from scripts.verify_artifacts import sha256_file, verify_artifact_tree
from whyback.observability import AuditEvent, AuditEventName

RUN_ID = UUID("00000000-0000-4000-8000-000000000077")


def _write_gate_project(root: Path) -> None:
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
default_reasoning_effort = "medium"
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


def _report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "product_name": "WhyBack",
        "tagline": "Find the why. Choose the way back.",
        "investigator_name": "WhyBack Investigator",
        "run_id": str(RUN_ID),
        "household_id": "77",
        "run_status": "completed",
        "decline": {
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
        "investigation_path": [],
        "likely_drivers": [],
        "supporting_evidence": [],
        "counterevidence": [],
        "evidence_ledger": [],
        "alternative_explanations": [],
        "uncertainties": [],
        "action": None,
        "limitations": [],
        "tool_warnings": [],
        "verification_issues": [],
        "failure_reason": None,
        "human_review_required": True,
    }


def _write_trace(path: Path, *, model: str = "scripted/whyback-v1") -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    events = (
        AuditEvent(
            timestamp=started,
            event=AuditEventName.RUN_STARTED,
            run_id=RUN_ID,
            household_id="77",
            details={"model": model},
        ),
        AuditEvent(
            timestamp=started + timedelta(seconds=1),
            event=AuditEventName.RUN_COMPLETED,
            run_id=RUN_ID,
            household_id="77",
            details={"status": "completed"},
        ),
    )
    path.write_text(
        "".join(f"{event.model_dump_json()}\n" for event in events),
        encoding="utf-8",
    )


def _write_valid_artifacts(root: Path) -> None:
    run_dir = root / "run-77"
    run_dir.mkdir(parents=True)
    report_path = run_dir / "report.json"
    trace_path = run_dir / "trace.jsonl"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")
    _write_trace(trace_path)
    manifest = {
        "schema_version": 1,
        "product_name": "WhyBack",
        "execution_mode": "scripted",
        "artifacts": [
            {
                "path": "run-77/report.json",
                "sha256": sha256_file(report_path),
                "execution_mode": "scripted",
            },
            {
                "path": "run-77/trace.jsonl",
                "sha256": sha256_file(trace_path),
                "execution_mode": "scripted",
            },
        ],
    }
    (root / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "live_status.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "skipped",
                "execution_mode": "skipped",
                "reason": "OPENAI_API_KEY was absent.",
            }
        ),
        encoding="utf-8",
    )


def test_source_tree_hash_is_stable_and_excludes_generated_artifacts(
    tmp_path: Path,
) -> None:
    _write_gate_project(tmp_path)
    first = source_tree_hash(tmp_path)
    generated = tmp_path / "artifacts" / "tests"
    generated.mkdir(parents=True)
    (generated / "test_audit.json").write_text("changed", encoding="utf-8")
    assert source_tree_hash(tmp_path) == first

    (tmp_path / "src" / "whyback" / "__init__.py").write_text(
        "VERSION = 1\n", encoding="utf-8"
    )
    assert source_tree_hash(tmp_path) != first


def test_test_output_validation_requires_branch_coverage_and_threshold(
    tmp_path: Path,
) -> None:
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
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _write_valid_artifacts(tmp_path)

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed
    assert result.execution_modes == ("scripted", "skipped")
    assert "run-77/report.json" in result.checked_files


def test_artifact_verifier_fails_closed_for_tampering_and_malformed_trace(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _write_valid_artifacts(tmp_path)
    (tmp_path / "run-77" / "report.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "run-77" / "trace.jsonl").write_text("not-json\n", encoding="utf-8")

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {issue.code for issue in result.issues}

    assert not result.passed
    assert "malformed_report" in codes
    assert "malformed_trace" in codes
    assert "file_hash_mismatch" in codes


def test_artifact_verifier_rejects_live_label_backed_by_scripted_trace(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _write_valid_artifacts(tmp_path)
    manifest_path = tmp_path / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution_mode"] = "live"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    codes = {issue.code for issue in result.issues}

    assert "live_label_mismatch" in codes
    assert "live_output_with_absent_credentials" in codes


def test_artifact_verifier_accepts_honest_skip_only_tree_with_explicit_flag(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    status_path = tmp_path / "live_model_status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "skipped_no_api_key",
                "execution_mode": "skipped",
                "reason": "OPENAI_API_KEY was absent.",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_mode": "skipped",
                "reason": "OPENAI_API_KEY was absent.",
                "files": {status_path.name: sha256_file(status_path)},
            }
        ),
        encoding="utf-8",
    )

    result = verify_artifact_tree(tmp_path, allow_live_skipped=True)

    assert result.passed
    assert result.execution_modes == ("skipped",)


class FakeRunner:
    def __init__(self, *, fail_sync: bool = False) -> None:
        self.fail_sync = fail_sync
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: tuple[str, ...], cwd: Path) -> ProcessResult:
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


def test_quality_gate_retains_preliminary_failure_and_runs_later_steps(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
    assert steps["deterministic_evals"]["status"] == "skipped"
    assert audit["test_summary"]["junit"]["tests"] == 7
    assert len(audit["invocations"]) == 1
    assert GatePaths.under(tmp_path).audit_json.is_file()
    assert GatePaths.under(tmp_path).audit_markdown.is_file()
    assert ("uv", "run", "pyright") in runner.commands

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
