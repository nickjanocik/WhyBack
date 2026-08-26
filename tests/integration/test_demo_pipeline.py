from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_artifacts import verify_artifact_tree
from whyback.demo import (
    _gemini_api_key_present,
    _initialize_live_official_output,
    build_official_demo,
    build_synthetic_demo,
)
from whyback.demo_limits import MAX_DEMO_CUSTOMERS, MIN_DEMO_CUSTOMERS
from whyback.observability import read_audit_events


def _normalized_trace(path: Path) -> dict[str, object]:
    normalized: list[dict[str, Any]] = []
    for event in read_audit_events(path):
        details = event.details
        if event.event.value == "evidence_added":
            metric = details.get("metric")
            if (
                normalized
                and normalized[-1]["event"] == "evidence_batch"
                and normalized[-1]["tool"] == details.get("source_tool")
            ):
                normalized[-1]["metrics"].append(metric)
            else:
                normalized.append(
                    {
                        "event": "evidence_batch",
                        "tool": details.get("source_tool"),
                        "metrics": [metric],
                    }
                )
            continue
        item: dict[str, Any] = {"event": event.event.value}
        for source, target in (
            ("tool_name", "tool"),
            ("selected_tool", "selected_tool"),
            ("status", "status"),
            ("attempt", "attempt"),
            ("next_attempt", "next_attempt"),
            ("next_best_action_id", "action"),
        ):
            value = details.get(source)
            if value is not None:
                item[target] = value
        if event.event.value in {"tool_completed", "tool_partial", "tool_failed"}:
            evidence_ids = details.get("evidence_ids", [])
            item["evidence_count"] = (
                len(evidence_ids) if isinstance(evidence_ids, list) else 0
            )
        normalized.append(item)
    return {"schema_version": 1, "normalized_events": normalized}


def test_synthetic_demo_reaches_verified_reports_and_safe_failure(
    tmp_path: Path,
) -> None:
    summary = build_synthetic_demo(tmp_path, customers=MIN_DEMO_CUSTOMERS)

    assert summary.selected_household_ids == ("101", "102", "103", "104", "105")
    assert summary.completed_household_ids == ("101", "102", "103", "104", "105")
    assert summary.report_count == MIN_DEMO_CUSTOMERS
    standard = json.loads(
        (tmp_path / "customer_101" / "report.json").read_text(encoding="utf-8")
    )
    assert standard["run_status"] == "completed"
    assert standard["action"]["human_review_required"] is True
    assert standard["provenance"]["dataset_kind"] == "synthetic"
    assert standard["provenance"]["execution_mode"] == "scripted_control"
    assert standard["provenance"]["dataset_source_repository"] == (
        "whyback/synthetic-fixture"
    )
    assert all("partial calendar weeks" not in item for item in standard["limitations"])

    failure = json.loads(
        (tmp_path / "failure_example" / "report.json").read_text(encoding="utf-8")
    )
    warning = failure["tool_warnings"][0]
    assert warning["tool_name"] == "promotion_response"
    assert warning["attempt_statuses"] == ["retryable_error", "retryable_error"]
    assert warning["retry_count"] == 1
    assert all(
        item["source_tool"] != "promotion_response"
        for item in failure["supporting_evidence"]
    )
    failure_events = read_audit_events(tmp_path / "failure_example" / "trace.jsonl")
    completed_tool = next(
        event for event in failure_events if event.event.value == "tool_completed"
    )
    complete_result = completed_tool.details["tool_result"]
    assert isinstance(complete_result, dict)
    assert complete_result["evidence"]
    provenance = complete_result["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["dataset_source_commit"]

    partial = json.loads(
        (tmp_path / "type_a_partial_example" / "report.json").read_text(
            encoding="utf-8"
        )
    )
    assert partial["tool_warnings"][0]["final_status"] == "partial"
    assert len(partial["counterevidence"]) == 1
    assert partial["counterevidence"][0]["source_tool"] == "peer_comparison"
    assert partial["counterevidence"][0]["metric"] == "context_classification"
    assert any("delivered coupon identities" in item for item in partial["limitations"])

    verification = verify_artifact_tree(tmp_path, allow_live_skipped=True)
    assert verification.passed, verification.issues


def test_synthetic_demo_supports_the_full_customer_maximum(tmp_path: Path) -> None:
    summary = build_synthetic_demo(tmp_path, customers=MAX_DEMO_CUSTOMERS)
    expected_ids = tuple(str(identifier) for identifier in range(101, 125))

    assert summary.selected_household_ids == expected_ids
    assert summary.completed_household_ids == expected_ids
    assert summary.report_count == MAX_DEMO_CUSTOMERS
    assert all(
        (tmp_path / f"customer_{household_id}" / "report.json").is_file()
        for household_id in expected_ids
    )


def test_persistent_failure_trace_matches_normalized_golden(tmp_path: Path) -> None:
    build_synthetic_demo(tmp_path, customers=MIN_DEMO_CUSTOMERS)
    actual = _normalized_trace(tmp_path / "failure_example" / "trace.jsonl")
    golden = json.loads(
        Path("tests/golden/failure_trace.normalized.json").read_text(encoding="utf-8")
    )

    assert actual == golden


def test_synthetic_demo_rerun_replaces_the_exact_owned_tree(tmp_path: Path) -> None:
    build_synthetic_demo(tmp_path, customers=MIN_DEMO_CUSTOMERS + 1)
    assert (tmp_path / "customer_106").is_dir()

    summary = build_synthetic_demo(tmp_path, customers=MIN_DEMO_CUSTOMERS)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert summary.selected_household_ids == ("101", "102", "103", "104", "105")
    assert not (tmp_path / "customer_106").exists()
    assert all("customer_106/" not in path for path in manifest["files"])


def test_synthetic_demo_refuses_to_replace_an_unowned_directory(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "valuable"
    destination.mkdir()
    note = destination / "keep.txt"
    note.write_text("must survive", encoding="utf-8")

    with pytest.raises(ValueError, match="not marked"):
        build_synthetic_demo(destination, customers=MIN_DEMO_CUSTOMERS)

    assert note.read_text(encoding="utf-8") == "must survive"


@pytest.mark.parametrize("customers", [MIN_DEMO_CUSTOMERS - 1, MAX_DEMO_CUSTOMERS + 1])
def test_demo_boundaries_fail_before_creating_output(
    tmp_path: Path,
    customers: int,
) -> None:
    synthetic_output = tmp_path / "synthetic"
    official_output = tmp_path / "official"

    with pytest.raises(ValueError, match="between 5 and 24"):
        build_synthetic_demo(synthetic_output, customers=customers)
    with pytest.raises(ValueError, match="between 5 and 24"):
        build_official_demo(
            tmp_path / "missing-prepared-data",
            official_output,
            customers=customers,
        )

    assert not synthetic_output.exists()
    assert not official_output.exists()


def test_live_official_transition_exactly_replaces_an_owned_skipped_tree(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "official"
    destination.mkdir()
    (destination / ".whyback-owned-artifact-root.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "WhyBack",
                "scope": "replaceable_generated_artifact_tree",
            }
        ),
        encoding="utf-8",
    )
    (destination / "live_model_status.json").write_text(
        json.dumps({"status": "skipped_no_api_key"}),
        encoding="utf-8",
    )
    (destination / "manifest.json").write_text("{}", encoding="utf-8")

    _initialize_live_official_output(destination)

    assert (destination / ".whyback-owned-artifact-root.json").is_file()
    assert not (destination / "live_model_status.json").exists()
    assert not (destination / "manifest.json").exists()


@pytest.mark.parametrize(
    ("value", "expected"),
    (("", False), ("   \t", False), ("test-placeholder", True)),
)
def test_gemini_key_presence_requires_non_space_text(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", value)

    assert _gemini_api_key_present() is expected


def test_live_official_transition_preserves_prior_run_artifacts(tmp_path: Path) -> None:
    destination = tmp_path / "official"
    customer = destination / "customer_181"
    customer.mkdir(parents=True)
    trace = customer / "trace.jsonl"
    trace.write_text("historical audit\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exist"):
        _initialize_live_official_output(destination)

    assert trace.read_text(encoding="utf-8") == "historical audit\n"
