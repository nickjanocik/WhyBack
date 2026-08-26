"""Tests for aggregate-only post-hoc demographic monitoring."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from scripts import audit_fairness
from whyback.data.manifest import DataManifest
from whyback.governance.fairness import (
    AttributeAudit,
    FairnessAudit,
    FairnessAuditPolicy,
    GroupRate,
    PipelineMembership,
    StageAudit,
    build_fairness_audit,
)


def _identifiers(prefix: str, count: int) -> tuple[str, ...]:
    """Build stable opaque identifiers for a hand-calculated cohort."""

    return tuple(f"{prefix}-{index:02d}" for index in range(count))


def _detector_memberships(
    *,
    observed: tuple[str, ...],
    eligible: tuple[str, ...],
    flagged: tuple[str, ...] = (),
) -> PipelineMembership:
    """Build detector-only memberships for concise unit tests."""

    return PipelineMembership(
        observed=frozenset(observed),
        eligible=frozenset(eligible),
        flagged=frozenset(flagged),
    )


def _attribute(audit: FairnessAudit, name: str = "age") -> AttributeAudit:
    """Return one named attribute from a validated audit."""

    return next(item for item in audit.attributes if item.attribute == name)


def _stage(attribute: AttributeAudit, name: str) -> StageAudit:
    """Return one named stage from an attribute audit."""

    return next(item for item in attribute.stages if item.stage == name)


def _group(stage: StageAudit, name: str) -> GroupRate:
    """Return one named demographic group from a stage audit."""

    return next(item for item in stage.groups if item.group == name)


def test_hand_calculated_rates_trigger_symmetric_review_heuristics() -> None:
    """Flag material lower and higher rates against the overall transition rate."""

    group_a = _identifiers("opaque-a", 20)
    group_b = _identifiers("opaque-b", 20)
    observed = (*group_a, *group_b)
    eligible = (*group_a[:4], *group_b[:8])
    demographics = pd.DataFrame(
        {
            "household_id": observed,
            "age": ("A",) * 20 + ("B",) * 20,
        }
    )

    audit = build_fairness_audit(
        demographics=demographics,
        memberships=_detector_memberships(observed=observed, eligible=eligible),
        attributes=("age",),
    )
    stage = _stage(_attribute(audit), "eligibility")
    lower = _group(stage, "A")
    higher = _group(stage, "B")

    assert stage.overall_rate == pytest.approx(0.30)
    assert lower.rate == pytest.approx(0.20)
    assert lower.rate_gap == pytest.approx(-0.10)
    assert lower.rate_ratio == pytest.approx(2 / 3)
    assert lower.review_recommended is True
    assert higher.rate == pytest.approx(0.40)
    assert higher.rate_gap == pytest.approx(0.10)
    assert higher.rate_ratio == pytest.approx(4 / 3)
    assert higher.review_recommended is True


def test_ratio_boundaries_are_not_outside_the_review_interval() -> None:
    """Keep exact ratio boundaries from producing a review recommendation."""

    group_a = _identifiers("boundary-a", 20)
    group_b = _identifiers("boundary-b", 20)
    observed = (*group_a, *group_b)
    eligible = (*group_a[:8], *group_b[:12])
    demographics = pd.DataFrame(
        {
            "household_id": observed,
            "age": ("A",) * 20 + ("B",) * 20,
        }
    )

    audit = build_fairness_audit(
        demographics=demographics,
        memberships=_detector_memberships(observed=observed, eligible=eligible),
        attributes=("age",),
    )
    lower = _group(_stage(_attribute(audit), "eligibility"), "A")

    assert lower.rate_gap == pytest.approx(-0.10)
    assert lower.rate_ratio == pytest.approx(0.80)
    assert lower.review_recommended is False


def test_minimum_group_size_applies_complementary_suppression() -> None:
    """Withhold every peer cell when one demographic denominator is too small."""

    small = _identifiers("small", 19)
    publishable = _identifiers("large", 20)
    observed = (*small, *publishable)
    demographics = pd.DataFrame(
        {
            "household_id": observed,
            "age": ("SMALL",) * 19 + ("LARGE",) * 20,
        }
    )
    memberships = _detector_memberships(
        observed=observed,
        eligible=(*small[:10], *publishable[:10]),
    )

    stage = _stage(
        _attribute(
            build_fairness_audit(
                demographics=demographics,
                memberships=memberships,
                attributes=("age",),
            )
        ),
        "eligibility",
    )
    suppressed = _group(stage, "SUPPRESSED")
    available = _group(stage, "LARGE")

    assert suppressed.status == "insufficient_sample"
    assert suppressed.denominator_count is None
    assert suppressed.numerator_count is None
    assert suppressed.rate is None
    assert suppressed.rate_gap is None
    assert suppressed.rate_ratio is None
    assert suppressed.review_recommended is False
    assert available.status == "insufficient_sample"
    assert available.denominator_count is None


def test_missing_rows_nulls_and_blanks_reconcile_to_unknown() -> None:
    """Retain every observed household and explain each UNKNOWN assignment."""

    observed = _identifiers("coverage", 25)
    demographics = pd.DataFrame(
        {
            "household_id": observed[:22],
            "age": ("35-44",) * 19 + (None, "", "unknown"),
        }
    )

    audit = build_fairness_audit(
        demographics=demographics,
        memberships=_detector_memberships(observed=observed, eligible=observed[:10]),
        attributes=("age",),
    )
    coverage = _attribute(audit)
    unknown = _group(_stage(_attribute(audit), "eligibility"), "UNKNOWN")

    assert coverage.observed_count == 25
    assert coverage.coverage_status == "insufficient_sample"
    assert coverage.known_value_count is None
    assert coverage.unknown_value_count is None
    assert coverage.missing_source_row_count is None
    assert coverage.missing_field_value_count is None
    assert coverage.coverage_rate is None
    assert unknown.status == "insufficient_sample"


def test_detector_only_audit_marks_absent_artifact_stages_unavailable() -> None:
    """Represent missing selection and outcomes as unavailable rather than zero."""

    observed = _identifiers("partial", 20)
    demographics = pd.DataFrame(
        {"household_id": observed, "age": ("A",) * len(observed)}
    )

    audit = build_fairness_audit(
        demographics=demographics,
        memberships=_detector_memberships(observed=observed, eligible=observed),
        attributes=("age",),
    )
    stages = _attribute(audit).stages

    assert audit.availability == "partial"
    assert [item.availability for item in stages[:2]] == ["available", "available"]
    for stage in stages[2:]:
        assert stage.availability == "unavailable"
        assert stage.overall_denominator_count is None
        assert stage.overall_numerator_count is None
        assert stage.overall_rate is None
        assert stage.groups == ()


def test_full_outcome_partition_and_zero_rate_are_explicit() -> None:
    """Publish exact zero outcomes while leaving a zero-reference ratio undefined."""

    observed = _identifiers("full", 20)
    selected = frozenset(observed[:4])
    memberships = PipelineMembership(
        observed=frozenset(observed),
        eligible=frozenset(observed),
        flagged=frozenset(observed[:10]),
        selected=selected,
        completed=frozenset(),
        insufficient_evidence=frozenset(observed[:2]),
        failed=frozenset(observed[2:4]),
        governed_action=frozenset(),
    )
    demographics = pd.DataFrame(
        {"household_id": observed, "age": ("A",) * len(observed)}
    )

    audit = build_fairness_audit(
        demographics=demographics,
        memberships=memberships,
        attributes=("age",),
    )
    completed = _stage(_attribute(audit), "completed")

    assert audit.availability == "full"
    assert completed.availability == "available"
    assert completed.overall_denominator_count == 4
    assert completed.overall_numerator_count == 0
    assert completed.overall_rate == 0.0
    assert _group(completed, "A").rate_ratio is None


def test_output_is_deterministic_aggregate_only_and_input_is_unchanged() -> None:
    """Exclude private IDs and leave the caller's demographic frame untouched."""

    observed = tuple(f"PRIVATE-HOUSEHOLD-{index}" for index in range(20))
    demographics = pd.DataFrame(
        {
            "household_id": observed,
            "age": ("B", "A") * 10,
        }
    )
    original = demographics.copy(deep=True)
    memberships = _detector_memberships(observed=observed, eligible=observed[:10])

    first = build_fairness_audit(
        demographics=demographics,
        memberships=memberships,
        attributes=("age",),
    )
    second = build_fairness_audit(
        demographics=demographics,
        memberships=memberships,
        attributes=("age",),
    )
    rendered = first.model_dump_json()
    decoded = json.loads(rendered)

    assert first == second
    assert_frame_equal(demographics, original)
    assert not any(identifier in rendered for identifier in observed)
    assert "run_id" not in rendered
    assert "household_id" not in rendered
    assert '"group":"A"' not in rendered
    assert '"group":"B"' not in rendered
    assert "SUPPRESSED" in rendered
    assert decoded["scope"] == "post_hoc_demographic_monitoring"
    assert all(
        "fair/unfair" not in item.casefold() or "not a fair/unfair" in item.casefold()
        for item in decoded["limitations"]
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"2"}),
            flagged=frozenset(),
        ),
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"1"}),
            flagged=frozenset({"2"}),
        ),
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"1"}),
            flagged=frozenset({"1"}),
            selected=frozenset({"2"}),
        ),
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"1"}),
            flagged=frozenset({"1"}),
            completed=frozenset({"1"}),
        ),
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"1"}),
            flagged=frozenset({"1"}),
            selected=frozenset({"1"}),
            completed=frozenset({"1"}),
        ),
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"1"}),
            flagged=frozenset({"1"}),
            selected=frozenset({"1"}),
            completed=frozenset({"1"}),
            insufficient_evidence=frozenset({"1"}),
            failed=frozenset(),
        ),
        lambda: PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset({"1"}),
            flagged=frozenset({"1"}),
            selected=frozenset({"1"}),
            completed=frozenset(),
            insufficient_evidence=frozenset(),
            failed=frozenset({"1"}),
            governed_action=frozenset({"1"}),
        ),
        lambda: PipelineMembership(
            observed=frozenset({" "}),
            eligible=frozenset(),
            flagged=frozenset(),
        ),
    ],
)
def test_pipeline_membership_rejects_inconsistent_private_sets(
    factory: Callable[[], PipelineMembership],
) -> None:
    """Fail closed for every invalid nested membership or outcome partition."""

    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize(
    ("demographics", "attributes"),
    [
        (pd.DataFrame({"age": ["A"]}), ("age",)),
        (
            pd.DataFrame({"household_id": ["1", "1"], "age": ["A", "A"]}),
            ("age",),
        ),
        (
            pd.DataFrame({"household_id": ["1"], "segment_code": ["unique"]}),
            ("segment_code",),
        ),
        (pd.DataFrame({"household_id": ["1"], "age": ["A"]}), ("missing",)),
        (pd.DataFrame({"household_id": ["1"], "age": ["A"]}), ("age", "age")),
        (pd.DataFrame({"household_id": ["1"], "age": ["A"]}), ("",)),
        (
            pd.DataFrame({"household_id": ["1"], "age": ["A"]}),
            ("household_id",),
        ),
    ],
)
def test_demographic_boundary_rejects_unsafe_or_malformed_inputs(
    demographics: pd.DataFrame,
    attributes: tuple[str, ...],
) -> None:
    """Reject missing identity, duplicates, and non-allowlisted output labels."""

    memberships = PipelineMembership(
        observed=frozenset({"1"}),
        eligible=frozenset(),
        flagged=frozenset(),
    )

    with pytest.raises(ValueError):
        build_fairness_audit(
            demographics=demographics,
            memberships=memberships,
            attributes=attributes,
        )


def test_no_supported_attributes_produces_an_honest_unavailable_audit() -> None:
    """Return an unavailable contract when only the join identifier exists."""

    audit = build_fairness_audit(
        demographics=pd.DataFrame({"household_id": ["1"]}),
        memberships=PipelineMembership(
            observed=frozenset({"1"}),
            eligible=frozenset(),
            flagged=frozenset(),
        ),
    )

    assert audit.availability == "unavailable"
    assert audit.attributes == ()
    assert "No supported demographic attributes" in audit.limitations[-1]


def test_unusual_scalar_value_is_rendered_without_breaking_unknown_handling() -> None:
    """Handle an object whose missingness check is not a scalar Boolean."""

    observed = _identifiers("object", 20)
    demographics = pd.DataFrame(
        {
            "household_id": observed,
            "age": [["A", "B"], *("A" for _ in range(19))],
        }
    )

    audit = build_fairness_audit(
        demographics=demographics,
        memberships=_detector_memberships(observed=observed, eligible=observed),
        attributes=("age",),
    )

    assert _attribute(audit).known_value_count == 20


def test_reserved_suppression_label_is_rejected_instead_of_merged() -> None:
    """Reject a source value that collides with the privacy aggregation label."""

    observed = _identifiers("reserved", 20)
    demographics = pd.DataFrame(
        {"household_id": observed, "age": ("SUPPRESSED",) * len(observed)}
    )

    with pytest.raises(ValueError, match="reserved"):
        build_fairness_audit(
            demographics=demographics,
            memberships=_detector_memberships(observed=observed, eligible=observed),
            attributes=("age",),
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"minimum_group_size": 19},
        {"rate_ratio_lower": 1.0, "rate_ratio_upper": 1.0},
    ],
)
def test_policy_rejects_unsafe_sample_and_ratio_boundaries(
    arguments: dict[str, float | int],
) -> None:
    """Reject relaxed sample privacy and an empty neutral ratio interval."""

    with pytest.raises(ValueError):
        FairnessAuditPolicy(**arguments)  # type: ignore[arg-type]


def test_fairness_output_guard_protects_inputs_and_symlink_chains(
    tmp_path: Path,
) -> None:
    """Keep optional JSON output outside prepared and artifact input trees."""

    prepared = tmp_path / "prepared"
    artifact = tmp_path / "artifact"
    prepared.mkdir()
    artifact.mkdir()

    with pytest.raises(ValueError, match="outside validated inputs"):
        audit_fairness._validate_output(
            prepared / "audit.json",
            (prepared, artifact),
        )

    target = tmp_path / "target.json"
    linked = tmp_path / "linked.json"
    linked.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        audit_fairness._validate_output(linked, (prepared, artifact))

    audit_fairness._validate_output(tmp_path / "audits" / "fairness.json", (prepared,))


def test_fairness_cli_minimizes_schema_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Avoid echoing validated input contents when a schema rejects them."""

    def reject_schema(*_args: object, **_kwargs: object) -> FairnessAudit:
        """Raise a validation error containing text that must remain private."""

        return FairnessAudit.model_validate({"private_input": "PRIVATE-HOUSEHOLD-999"})

    monkeypatch.setattr(audit_fairness, "_build", reject_schema)

    assert audit_fairness.main(["--prepared-dir", str(tmp_path)]) == 1
    error = capsys.readouterr().err
    assert "validated schema" in error
    assert "PRIVATE-HOUSEHOLD-999" not in error


def test_artifact_outcomes_must_match_the_exact_prepared_manifest() -> None:
    """Reject verified outcomes when the local prepared manifest hash differs."""

    root = Path(__file__).resolve().parents[2]
    pointer = json.loads(
        (root / "artifacts" / "default-live-run.json").read_text(encoding="utf-8")
    )
    artifact = root / "artifacts" / "local" / "live-runs" / pointer["collection_id"]
    artifact_manifest = json.loads(
        (artifact / "manifest.json").read_text(encoding="utf-8")
    )
    manifest = DataManifest(
        source_repository=artifact_manifest["dataset_source_repository"],
        source_commit=artifact_manifest["dataset_source_commit"],
        preparation_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        preparation_code_sha256="0" * 64,
        source_tree_version="clean-checkout-test",
        source_tree_dirty=False,
        sources=(),
        prepared=(),
        diagnostics={},
    )

    with pytest.raises(ValueError, match="prepared-data manifest"):
        audit_fairness._artifact_context(artifact, manifest, "0" * 64)
