"""Tests for additive, identifier-minimized operational health and drift audits."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest

from scripts.audit_operations import main as operations_main
from whyback.observability.operations import (
    DEFAULT_MINIMUM_RUNS,
    DriftStatus,
    OperationalInputStatus,
    compare_operational_cohorts,
    kolmogorov_smirnov_distance,
    summarize_numeric,
    summarize_operational_health,
    total_variation_distance,
)

ROOT = Path(__file__).resolve().parents[2]
STANDARD_RUN = ROOT / "artifacts" / "demo" / "customer_101"
RETRY_RUN = ROOT / "artifacts" / "demo" / "failure_example"


def _pair(
    source: Path,
    destination: Path,
    index: int,
    mutate: Callable[[Path], None] | None = None,
) -> Path:
    """Copy a verified pair with a unique run identity into a test cohort."""

    destination.mkdir(parents=True)
    report_text = (source / "report.json").read_text(encoding="utf-8")
    original_id = str(json.loads(report_text)["run_id"])
    replacement = str(UUID(int=10_000 + index))
    (destination / "report.json").write_text(
        report_text.replace(original_id, replacement),
        encoding="utf-8",
    )
    trace_text = (source / "trace.jsonl").read_text(encoding="utf-8")
    (destination / "trace.jsonl").write_text(
        trace_text.replace(original_id, replacement),
        encoding="utf-8",
    )
    if mutate is not None:
        mutate(destination)
    return destination


def _cohort(
    root: Path,
    count: int,
    *,
    changed: frozenset[int] = frozenset(),
    model: str | None = None,
) -> Path:
    """Create a cohort with optional latency or compatibility changes."""

    for index in range(count):
        run = _pair(STANDARD_RUN, root / f"run_{index:02d}", index)
        if index in changed:
            _change_received_latency(run, 10_000.0)
        if model is not None:
            _change_model(run, model)
    return root


def _trace_documents(run: Path) -> list[dict[str, object]]:
    """Read one copied trace as mutable JSON documents."""

    return [
        json.loads(line)
        for line in (run / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def _write_trace(run: Path, documents: list[dict[str, object]]) -> None:
    """Persist compact JSONL after a test-local mutation."""

    rendered = "".join(
        f"{json.dumps(document, separators=(',', ':'))}\n" for document in documents
    )
    (run / "trace.jsonl").write_text(rendered, encoding="utf-8")


def _details(document: dict[str, object]) -> dict[str, object]:
    """Narrow one event's details for test-local mutation."""

    details = document["details"]
    assert isinstance(details, dict)
    return details


def _change_received_latency(run: Path, increment: float) -> None:
    """Shift recorded model latency without changing cohort compatibility."""

    documents = _trace_documents(run)
    for document in documents:
        if document["event"] == "model_decision_received":
            details = _details(document)
            latency = details["latency_ms"]
            assert isinstance(latency, (int, float)) and not isinstance(latency, bool)
            details["latency_ms"] = float(latency) + increment
    _write_trace(run, documents)


def _change_model(run: Path, model: str) -> None:
    """Change the report and trace model identity consistently."""

    report_path = run / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["provenance"]["model"] = model
    report_path.write_text(json.dumps(report), encoding="utf-8")
    documents = _trace_documents(run)
    for document in documents:
        details = _details(document)
        if "model" in details:
            details["model"] = model
    _write_trace(run, documents)


def _remove_input_tokens(run: Path) -> None:
    """Remove one recorded usage component to exercise coverage accounting."""

    documents = _trace_documents(run)
    for document in documents:
        if document["event"] == "model_decision_received":
            _details(document).pop("input_tokens", None)
    _write_trace(run, documents)


def _remove_tool_measurements(run: Path) -> None:
    """Remove tool measurements to distinguish absence from recorded zero."""

    documents = _trace_documents(run)
    terminal = {"tool_completed", "tool_partial", "tool_failed"}
    for document in documents:
        if document["event"] in terminal:
            details = _details(document)
            details.pop("latency_ms", None)
            details.pop("rows_examined", None)
    _write_trace(run, documents)


def _insert_operational_events(run: Path) -> None:
    """Add safe rejection and duplicate-refusal events before completion."""

    documents = _trace_documents(run)
    insertion = next(
        index
        for index, document in enumerate(documents)
        if document["event"] == "verification_started"
    )
    template = documents[insertion]
    common = {
        "schema_version": template["schema_version"],
        "timestamp": template["timestamp"],
        "run_id": template["run_id"],
        "household_id": template["household_id"],
    }
    documents[insertion:insertion] = [
        {
            **common,
            "event": "verification_started",
            "details": {"repair_attempted": True},
        },
        {
            **common,
            "event": "verification_rejected",
            "details": {"issues": [{"code": "unknown_evidence", "message": "safe"}]},
        },
        {
            **common,
            "event": "tool_failed",
            "details": {
                "tool_name": "customer_trend",
                "status": "invalid_request",
                "duplicate_refused": True,
            },
        },
    ]
    _write_trace(run, documents)


def _insert_untrusted_issue_code(run: Path) -> None:
    """Insert a structurally valid rejection carrying an untrusted code label."""

    documents = _trace_documents(run)
    insertion = next(
        index
        for index, document in enumerate(documents)
        if document["event"] == "verification_started"
    )
    template = documents[insertion]
    common = {
        "schema_version": template["schema_version"],
        "timestamp": template["timestamp"],
        "run_id": template["run_id"],
        "household_id": template["household_id"],
    }
    documents[insertion:insertion] = [
        {**common, "event": "verification_started", "details": {}},
        {
            **common,
            "event": "verification_rejected",
            "details": {
                "issues": [{"code": "PRIVATE-HOUSEHOLD-999", "message": "private"}]
            },
        },
    ]
    _write_trace(run, documents)


def test_distribution_distances_and_summaries_are_exact() -> None:
    """Verify deterministic summaries, TV distance, KS distance, and ties."""

    assert summarize_numeric([]) == {"count": 0}
    summary = summarize_numeric([0, 10])
    assert summary["p50"] == 5.0
    assert summary["maximum"] == 10.0
    assert total_variation_distance(["a", "a"], ["a", "b"]) == 0.5
    assert total_variation_distance(["a"], ["b"]) == 1.0
    assert kolmogorov_smirnov_distance([0, 0, 1], [0, 1, 1]) == pytest.approx(1 / 3)
    assert kolmogorov_smirnov_distance([0], [1]) == 1.0


def test_distances_reject_empty_samples() -> None:
    """Require both cohorts before reporting a distribution distance."""

    with pytest.raises(ValueError, match="nonempty"):
        total_variation_distance([], ["a"])
    with pytest.raises(ValueError, match="nonempty"):
        kolmogorov_smirnov_distance([], [1.0])


def test_numeric_helpers_reject_nonfinite_values() -> None:
    """Prevent non-JSON numeric values from reaching output documents."""

    with pytest.raises(ValueError, match="finite"):
        summarize_numeric([float("inf")])
    with pytest.raises(ValueError, match="finite"):
        kolmogorov_smirnov_distance([0.0], [float("nan")])


def test_summary_reads_explicit_pair_and_minimizes_identifiers(tmp_path: Path) -> None:
    """Aggregate one pair without leaking customer, run, or path identifiers."""

    run = _pair(STANDARD_RUN, tmp_path / "customer_181", 1)
    report = summarize_operational_health(run / "trace.jsonl")
    rendered = report.model_dump_json()

    assert report.status is OperationalInputStatus.READY
    assert report.valid_run_count == 1
    assert report.categorical_metrics["run_status"] == {"completed": 1}
    assert report.rates["tool_partial_rate"]["numerator"] == 1
    assert report.per_tool_metrics["customer_trend"]["attempts"] == 1
    assert "customer_181" not in rendered
    model_ref = report.model_dump()["compatibility"]["model_sha256"]
    assert isinstance(model_ref, str) and len(model_ref) == 64
    assert "scripted/whyback-v1" not in rendered
    assert str(UUID(int=10_001)) not in rendered
    with pytest.raises(TypeError, match="immutable"):
        report.rates["valid_input_rate"]["value"] = 0.0


def test_missing_usage_is_coverage_not_a_fabricated_zero(tmp_path: Path) -> None:
    """Suppress incomplete per-run token totals and expose their coverage."""

    run = _pair(STANDARD_RUN, tmp_path / "run", 2, _remove_input_tokens)
    report = summarize_operational_health(run)

    assert report.status is OperationalInputStatus.READY
    assert report.numeric_metrics["recorded_input_tokens_per_run"] == {"count": 0}
    assert report.rates["model_usage_coverage_rate"]["value"] == 0.0


def test_missing_tool_measurements_are_not_fabricated_as_zero(tmp_path: Path) -> None:
    """Keep absent tool latency and row measurements out of distributions."""

    run = _pair(STANDARD_RUN, tmp_path / "run", 22, _remove_tool_measurements)
    report = summarize_operational_health(run)

    assert report.numeric_metrics["recorded_tool_latency_ms_per_run"] == {"count": 0}
    assert report.numeric_metrics["recorded_rows_examined_per_run"] == {"count": 0}


def test_retries_rejections_and_refusals_use_explicit_denominators(
    tmp_path: Path,
) -> None:
    """Count retry attempts, verifier issue codes, and nonexecuted refusals."""

    retry = _pair(RETRY_RUN, tmp_path / "retry", 3)
    _insert_operational_events(retry)
    report = summarize_operational_health(tmp_path)

    assert report.status is OperationalInputStatus.READY
    assert report.rates["tool_retry_rate"]["numerator"] == 1
    assert report.rates["tool_error_rate"]["numerator"] == 3
    assert report.categorical_metrics["verification_issue_code"] == {
        "unknown_evidence": 1
    }
    trend = report.per_tool_metrics["customer_trend"]
    status_counts = trend["status_counts"]
    assert isinstance(status_counts, dict)
    assert status_counts["invalid_request"] == 1


def test_empty_partial_duplicate_and_invalid_inputs_are_visible_and_private(
    tmp_path: Path,
) -> None:
    """Classify unsafe roots without exposing their customer-bearing input text."""

    empty = tmp_path / "empty"
    empty.mkdir()
    assert summarize_operational_health(empty).status is OperationalInputStatus.INVALID

    root = tmp_path / "cohort"
    first = _pair(STANDARD_RUN, root / "valid", 4)
    duplicate = root / "duplicate_customer_181"
    duplicate.mkdir(parents=True)
    (duplicate / "report.json").write_bytes((first / "report.json").read_bytes())
    (duplicate / "trace.jsonl").write_bytes((first / "trace.jsonl").read_bytes())
    malformed = root / "secret_customer_181"
    malformed.mkdir()
    (malformed / "trace.jsonl").write_text(
        '{"household_id":"181","api_key":"must-not-leak"}\n',
        encoding="utf-8",
    )
    orphan = root / "orphan_report"
    orphan.mkdir()
    (orphan / "report.json").write_bytes((first / "report.json").read_bytes())
    report = summarize_operational_health(root)
    rendered = report.model_dump_json()

    assert report.status is OperationalInputStatus.PARTIAL
    assert report.discovered_run_count == 4
    assert report.valid_run_count == 1
    assert {issue["code"] for issue in report.issues} == {
        "duplicate_run",
        "missing_report",
        "missing_trace",
    }
    assert "customer_181" not in rendered
    assert '"household_id"' not in rendered
    assert "must-not-leak" not in rendered
    assert str(root) not in rendered
    with pytest.raises(TypeError, match="immutable"):
        report.issues[0]["code"] = "changed"


def test_lifecycle_and_metric_corruption_quarantine_the_pair(tmp_path: Path) -> None:
    """Fail closed on ownership changes and negative operational measurements."""

    ownership = _pair(STANDARD_RUN, tmp_path / "ownership", 5)
    documents = _trace_documents(ownership)
    documents[-1]["household_id"] = "different-customer"
    _write_trace(ownership, documents)

    metric = _pair(STANDARD_RUN, tmp_path / "metric", 6)
    documents = _trace_documents(metric)
    received = next(
        item for item in documents if item["event"] == "model_decision_received"
    )
    _details(received)["latency_ms"] = -1
    _write_trace(metric, documents)

    overflow = _pair(STANDARD_RUN, tmp_path / "overflow", 32)
    documents = _trace_documents(overflow)
    received = next(
        item for item in documents if item["event"] == "model_decision_received"
    )
    _details(received)["input_tokens"] = 10**400
    _write_trace(overflow, documents)

    sequence = _pair(STANDARD_RUN, tmp_path / "sequence", 33)
    documents = _trace_documents(sequence)
    requested = next(
        item for item in documents if item["event"] == "model_decision_requested"
    )
    requested["event"] = "model_decision_received"
    _write_trace(sequence, documents)

    report = summarize_operational_health(tmp_path)
    assert report.status is OperationalInputStatus.INVALID
    assert report.invalid_run_count == 4
    assert {issue["code"] for issue in report.issues} == {"invalid_pair"}


def test_untrusted_verifier_codes_are_quarantined_without_disclosure(
    tmp_path: Path,
) -> None:
    """Reject free-text issue codes before they can enter aggregate output."""

    run = _pair(STANDARD_RUN, tmp_path / "private_issue", 34)
    _insert_untrusted_issue_code(run)

    report = summarize_operational_health(tmp_path)
    rendered = report.model_dump_json()

    assert report.status is OperationalInputStatus.INVALID
    assert "PRIVATE-HOUSEHOLD-999" not in rendered
    assert "private_issue" not in rendered


def test_mixed_compatibility_is_not_silently_aggregated(tmp_path: Path) -> None:
    """Expose mixed workload identities instead of publishing one cohort key."""

    _pair(STANDARD_RUN, tmp_path / "one", 7)
    changed = _pair(STANDARD_RUN, tmp_path / "two", 8)
    _change_model(changed, "different-model")
    report = summarize_operational_health(tmp_path)

    assert report.status is OperationalInputStatus.MIXED_COHORT
    assert report.compatibility is None
    assert report.issues[-1]["code"] == "mixed_compatibility"


def test_comparison_requires_twenty_compatible_valid_runs(tmp_path: Path) -> None:
    """Apply the hard sample floor before running any distribution test."""

    baseline = _cohort(tmp_path / "baseline", DEFAULT_MINIMUM_RUNS - 1)
    current = _cohort(tmp_path / "current", DEFAULT_MINIMUM_RUNS - 1)
    report = compare_operational_cohorts(baseline, current)

    assert report.status is DriftStatus.INSUFFICIENT
    assert report.metrics == ()
    with pytest.raises(ValueError, match="lower than 20"):
        compare_operational_cohorts(baseline, current, minimum_runs=19)
    with pytest.raises(ValueError, match="unit interval"):
        compare_operational_cohorts(
            baseline,
            current,
            distance_threshold=float("nan"),
        )


def test_comparison_reports_stable_and_metric_level_insufficiency(
    tmp_path: Path,
) -> None:
    """Assess recorded metrics while retaining sparse-category limitations."""

    baseline = _cohort(tmp_path / "baseline", DEFAULT_MINIMUM_RUNS)
    current = _cohort(tmp_path / "current", DEFAULT_MINIMUM_RUNS)
    report = compare_operational_cohorts(baseline, current)

    assert report.status is DriftStatus.STABLE
    assert any(item["status"] == "stable" for item in report.metrics)
    issue_metric = next(
        item for item in report.metrics if item["name"] == "verification_issue_code"
    )
    assert issue_metric["status"] == "insufficient"
    assert issue_metric["distance"] is None
    with pytest.raises(TypeError, match="immutable"):
        report.metrics[0]["status"] = "detected"


def test_comparison_detects_the_inclusive_point_two_boundary(tmp_path: Path) -> None:
    """Treat an empirical distance of exactly 0.20 as detected drift."""

    baseline = _cohort(tmp_path / "baseline", DEFAULT_MINIMUM_RUNS)
    changed = frozenset(range(4))
    current = _cohort(
        tmp_path / "current",
        DEFAULT_MINIMUM_RUNS,
        changed=changed,
    )
    report = compare_operational_cohorts(baseline, current)
    latency = next(
        item
        for item in report.metrics
        if item["name"] == "recorded_model_latency_ms_per_run"
    )

    assert latency["distance"] == pytest.approx(0.20)
    assert latency["status"] == "detected"
    assert report.status is DriftStatus.DETECTED


def test_comparison_rejects_incompatible_and_mixed_roots(tmp_path: Path) -> None:
    """Perform no drift math when recorded workload identities differ or mix."""

    baseline = _cohort(tmp_path / "baseline", 1)
    current = _cohort(tmp_path / "current", 1, model="different-model")
    incompatible = compare_operational_cohorts(baseline, current)
    assert incompatible.status is DriftStatus.INCOMPATIBLE
    assert incompatible.metrics == ()

    mixed = tmp_path / "mixed"
    _pair(STANDARD_RUN, mixed / "one", 20)
    changed = _pair(STANDARD_RUN, mixed / "two", 21)
    _change_model(changed, "different-model")
    result = compare_operational_cohorts(mixed, baseline)
    assert result.status is DriftStatus.INCOMPATIBLE


def test_cli_stdout_atomic_output_guards_and_exit_semantics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep stdout useful while protecting sealed input trees from output writes."""

    run = _pair(STANDARD_RUN, tmp_path / "input", 30)
    assert operations_main(["summarize", str(run)]) == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["status"] == "ready"

    output = tmp_path / "output" / "health.json"
    assert operations_main(["summarize", str(run), "--json-output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["valid_run_count"] == 1
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []

    protected = run / "audit.json"
    assert (
        operations_main(["summarize", str(run), "--json-output", str(protected)]) == 1
    )
    assert not protected.exists()
    assert "input or output was unsafe" in capsys.readouterr().err


def test_cli_require_assessment_and_argument_guards(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Make drift gating opt-in while keeping the minimum sample floor fixed."""

    baseline = _cohort(tmp_path / "baseline", 1)
    current = _cohort(tmp_path / "current", 1)
    arguments = ["compare", str(baseline), str(current)]
    assert operations_main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "insufficient"
    assert operations_main([*arguments, "--require-assessment"]) == 1
    capsys.readouterr()

    with pytest.raises(SystemExit) as error:
        operations_main([*arguments, "--minimum-runs", "19"])
    assert error.value.code == 2


def test_cli_refuses_symlinked_output(tmp_path: Path) -> None:
    """Refuse a destination symlink before an operational document is written."""

    run = _pair(STANDARD_RUN, tmp_path / "input", 31)
    target = tmp_path / "target.json"
    output = tmp_path / "linked.json"
    output.symlink_to(target)

    assert operations_main(["summarize", str(run), "--json-output", str(output)]) == 1
    assert not target.exists()
