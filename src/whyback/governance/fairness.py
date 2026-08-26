"""Aggregate-only, post-hoc demographic monitoring for WhyBack cohorts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isclose
from typing import Literal, Self, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from whyback.config import DetectionConfig
from whyback.data.contracts import normalize_identifier

UNKNOWN_GROUP = "UNKNOWN"
SUPPRESSED_GROUP = "SUPPRESSED"
DEFAULT_DEMOGRAPHIC_ATTRIBUTES = (
    "age",
    "income",
    "home_ownership",
    "marital_status",
    "household_size",
    "household_comp",
    "kids_count",
)

type StageId = Literal[
    "eligibility",
    "flagging",
    "selection",
    "completed",
    "insufficient_evidence",
    "failed",
    "governed_action",
]


class FairnessAuditPolicy(BaseModel):
    """Declare conservative sample-size and descriptive review thresholds."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    minimum_group_size: int = Field(default=20, ge=20)
    absolute_rate_gap_threshold: float = Field(default=0.10, gt=0.0, le=1.0)
    rate_ratio_lower: float = Field(default=0.80, gt=0.0, le=1.0)
    rate_ratio_upper: float = Field(default=1.25, ge=1.0)

    @model_validator(mode="after")
    def validate_ratio_interval(self) -> Self:
        """Require an increasing comparison interval around a neutral ratio."""

        if self.rate_ratio_lower >= self.rate_ratio_upper:
            raise ValueError("Rate-ratio bounds must form an increasing interval")
        return self


class FairnessAuditProvenance(BaseModel):
    """Record source identity without run, household, or path identifiers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_source_repository: str = Field(min_length=1)
    dataset_source_commit: str = Field(min_length=1)
    prepared_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    detector_policy: DetectionConfig
    baseline_start_week: int = Field(ge=1, le=53)
    baseline_end_week: int = Field(ge=1, le=53)
    recent_start_week: int = Field(ge=1, le=53)
    recent_end_week: int = Field(ge=1, le=53)
    backend: str | None = None
    execution_mode: str | None = None


class GroupRate(BaseModel):
    """Publish one large-enough group rate or an explicit suppression marker."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    group: str = Field(min_length=1)
    status: Literal["available", "insufficient_sample"]
    denominator_count: int | None = Field(default=None, ge=0)
    numerator_count: int | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0.0, le=1.0)
    rate_gap: float | None = Field(default=None, ge=-1.0, le=1.0)
    rate_ratio: float | None = Field(default=None, ge=0.0)
    review_recommended: bool = False


class StageAudit(BaseModel):
    """Describe one pipeline transition and its single-attribute group rates."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    stage: StageId
    denominator_stage: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    availability: Literal["available", "unavailable"]
    unavailable_reason: str | None = None
    overall_denominator_count: int | None = Field(default=None, ge=0)
    overall_numerator_count: int | None = Field(default=None, ge=0)
    overall_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    groups: tuple[GroupRate, ...] = ()


class AttributeAudit(BaseModel):
    """Collect coverage and pipeline rates for one demographic attribute."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    attribute: str = Field(min_length=1)
    observed_count: int = Field(ge=0)
    coverage_status: Literal["available", "insufficient_sample"]
    known_value_count: int | None = Field(default=None, ge=0)
    unknown_value_count: int | None = Field(default=None, ge=0)
    missing_source_row_count: int | None = Field(default=None, ge=0)
    missing_field_value_count: int | None = Field(default=None, ge=0)
    coverage_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    stages: tuple[StageAudit, ...]


class FairnessAudit(BaseModel):
    """Versioned aggregate output that contains no household-level records."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal[1] = 1
    scope: Literal["post_hoc_demographic_monitoring"] = (
        "post_hoc_demographic_monitoring"
    )
    availability: Literal["full", "partial", "unavailable"]
    policy: FairnessAuditPolicy
    observed_household_count: int = Field(ge=0)
    demographic_source_row_count: int = Field(ge=0)
    attributes: tuple[AttributeAudit, ...]
    provenance: FairnessAuditProvenance | None = None
    limitations: tuple[str, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class PipelineMembership:
    """Hold private household memberships used only for aggregate calculation."""

    observed: frozenset[str]
    eligible: frozenset[str]
    flagged: frozenset[str]
    selected: frozenset[str] | None = None
    completed: frozenset[str] | None = None
    insufficient_evidence: frozenset[str] | None = None
    failed: frozenset[str] | None = None
    governed_action: frozenset[str] | None = None

    def __post_init__(self) -> None:
        """Reject blank identifiers and inconsistent nested memberships."""

        values = (
            self.observed,
            self.eligible,
            self.flagged,
            self.selected,
            self.completed,
            self.insufficient_evidence,
            self.failed,
            self.governed_action,
        )
        if any(not item.strip() for group in values if group for item in group):
            raise ValueError("Pipeline memberships require nonblank identifiers")
        if not self.eligible <= self.observed or not self.flagged <= self.eligible:
            raise ValueError("Detector memberships must be nested")
        outcomes = (self.completed, self.insufficient_evidence, self.failed)
        if self.selected is None:
            if any(item is not None for item in (*outcomes, self.governed_action)):
                raise ValueError("Outcome memberships require a selected cohort")
            return
        if not self.selected <= self.flagged:
            raise ValueError("Selected membership must be a subset of flagged")
        if any(item is not None for item in outcomes) and not all(
            item is not None for item in outcomes
        ):
            raise ValueError("Selected outcome memberships must be provided together")
        if all(item is not None for item in outcomes):
            completed, insufficient, failed = cast(
                tuple[frozenset[str], frozenset[str], frozenset[str]], outcomes
            )
            if (
                completed & insufficient
                or completed & failed
                or insufficient & failed
                or completed | insufficient | failed != self.selected
            ):
                raise ValueError("Selected outcomes must form an exact partition")
        if self.governed_action is not None and (
            self.completed is None or not self.governed_action <= self.completed
        ):
            raise ValueError("Governed actions must be completed outcomes")


@dataclass(frozen=True, slots=True)
class _Stage:
    """Associate a public transition with private denominator and numerator sets."""

    stage: StageId
    denominator_stage: str
    definition: str
    denominator: frozenset[str] | None
    numerator: frozenset[str] | None


_STAGE_METADATA: Mapping[StageId, tuple[str, str]] = {
    "eligibility": (
        "observed",
        "Observed households meeting the detector eligibility policy.",
    ),
    "flagging": (
        "eligible",
        "Eligible households meeting the decline-score threshold.",
    ),
    "selection": (
        "flagged",
        "Flagged households selected for an investigation batch.",
    ),
    "completed": (
        "selected",
        "Selected households ending with a verified supported action.",
    ),
    "insufficient_evidence": (
        "selected",
        "Selected households ending with the governed fallback.",
    ),
    "failed": (
        "selected",
        "Selected households ending without a publishable result.",
    ),
    "governed_action": (
        "selected",
        "Selected households receiving a supported non-fallback action.",
    ),
}


def _stages(membership: PipelineMembership) -> tuple[_Stage, ...]:
    """Resolve detector, selection, outcome, and governed-action transitions."""

    selected = membership.selected
    outcomes_available = all(
        item is not None
        for item in (
            membership.completed,
            membership.insufficient_evidence,
            membership.failed,
        )
    )
    outcome_denominator = selected if outcomes_available else None
    sets: tuple[tuple[StageId, frozenset[str] | None, frozenset[str] | None], ...] = (
        ("eligibility", membership.observed, membership.eligible),
        ("flagging", membership.eligible, membership.flagged),
        ("selection", membership.flagged if selected is not None else None, selected),
        ("completed", outcome_denominator, membership.completed),
        (
            "insufficient_evidence",
            outcome_denominator,
            membership.insufficient_evidence,
        ),
        ("failed", outcome_denominator, membership.failed),
        (
            "governed_action",
            selected if membership.governed_action is not None else None,
            membership.governed_action,
        ),
    )
    return tuple(
        _Stage(stage, *_STAGE_METADATA[stage], denominator, numerator)
        for stage, denominator, numerator in sets
    )


def _attributes(
    frame: pd.DataFrame, requested: Sequence[str] | None
) -> tuple[str, ...]:
    """Resolve only fixed, low-cardinality demographic attributes."""

    columns = {str(item) for item in frame.columns}
    if requested is None:
        return tuple(item for item in DEFAULT_DEMOGRAPHIC_ATTRIBUTES if item in columns)
    selected = tuple(item.strip() for item in requested)
    if any(not item for item in selected) or len(selected) != len(set(selected)):
        raise ValueError("Requested demographic attributes must be unique and nonblank")
    if "household_id" in selected:
        raise ValueError("household_id is not a demographic audit attribute")
    if set(selected) - columns:
        raise ValueError("Requested demographic attributes are unavailable")
    if set(selected) - set(DEFAULT_DEMOGRAPHIC_ATTRIBUTES):
        raise ValueError("Requested attributes are outside the safe allowlist")
    return selected


def _rows(frame: pd.DataFrame) -> Mapping[str, Mapping[str, object]]:
    """Build a unique private demographic lookup from the prepared frame."""

    if "household_id" not in frame.columns:
        raise ValueError("Demographics require a household_id column")
    rows: dict[str, Mapping[str, object]] = {}
    records = cast(list[dict[str, object]], frame.to_dict(orient="records"))
    for record in records:
        identifier = normalize_identifier(record["household_id"])
        if identifier in rows:
            raise ValueError("Demographics contain duplicate household identifiers")
        rows[identifier] = record
    return rows


def _value(value: object) -> str:
    """Normalize absent or blank demographic values to UNKNOWN."""

    if value is None or value is pd.NA:
        return UNKNOWN_GROUP
    try:
        if bool(pd.isna(value)):
            return UNKNOWN_GROUP
    except (TypeError, ValueError):
        pass
    rendered = str(value).strip()
    if not rendered or rendered.casefold() == UNKNOWN_GROUP.casefold():
        return UNKNOWN_GROUP
    if rendered.casefold() == SUPPRESSED_GROUP.casefold():
        raise ValueError("SUPPRESSED is reserved for privacy aggregation")
    return rendered


def _group_rate(
    group: str,
    stage: _Stage,
    assignments: Mapping[str, str],
    overall_rate: float,
    policy: FairnessAuditPolicy,
    *,
    complementary_suppression: bool,
) -> GroupRate:
    """Calculate one group rate after enforcing the sample-size boundary."""

    denominator = cast(frozenset[str], stage.denominator)
    numerator = cast(frozenset[str], stage.numerator)
    denominator_count = sum(assignments[item] == group for item in denominator)
    if complementary_suppression or denominator_count < policy.minimum_group_size:
        return GroupRate(group=group, status="insufficient_sample")
    numerator_count = sum(assignments[item] == group for item in numerator)
    rate = numerator_count / denominator_count
    gap = rate - overall_rate
    ratio = rate / overall_rate if overall_rate else None
    below = (
        ratio is not None
        and ratio < policy.rate_ratio_lower
        and not isclose(ratio, policy.rate_ratio_lower)
    )
    above = (
        ratio is not None
        and ratio > policy.rate_ratio_upper
        and not isclose(ratio, policy.rate_ratio_upper)
    )
    material = abs(gap) > policy.absolute_rate_gap_threshold or isclose(
        abs(gap), policy.absolute_rate_gap_threshold
    )
    return GroupRate(
        group=group,
        status="available",
        denominator_count=denominator_count,
        numerator_count=numerator_count,
        rate=rate,
        rate_gap=gap,
        rate_ratio=ratio,
        review_recommended=material and (below or above),
    )


def _stage_audit(
    stage: _Stage,
    assignments: Mapping[str, str],
    policy: FairnessAuditPolicy,
) -> StageAudit:
    """Aggregate one transition without retaining an identifier in its result."""

    if stage.denominator is None or stage.numerator is None:
        return StageAudit(
            stage=stage.stage,
            denominator_stage=stage.denominator_stage,
            definition=stage.definition,
            availability="unavailable",
            unavailable_reason=(
                "No compatible verified artifact outcomes were supplied."
            ),
        )
    denominator_count = len(stage.denominator)
    numerator_count = len(stage.numerator)
    overall_rate = numerator_count / denominator_count if denominator_count else 0.0
    groups = sorted(
        set(assignments.values()), key=lambda item: (item != UNKNOWN_GROUP, item)
    )
    denominator_counts = {
        group: sum(assignments[item] == group for item in stage.denominator)
        for group in groups
    }
    complementary_suppression = any(
        0 < count < policy.minimum_group_size for count in denominator_counts.values()
    )
    return StageAudit(
        stage=stage.stage,
        denominator_stage=stage.denominator_stage,
        definition=stage.definition,
        availability="available",
        overall_denominator_count=denominator_count,
        overall_numerator_count=numerator_count,
        overall_rate=overall_rate,
        groups=tuple(
            _group_rate(
                group,
                stage,
                assignments,
                overall_rate,
                policy,
                complementary_suppression=complementary_suppression,
            )
            for group in groups
        ),
    )


def build_fairness_audit(
    *,
    demographics: pd.DataFrame,
    memberships: PipelineMembership,
    attributes: Sequence[str] | None = None,
    policy: FairnessAuditPolicy | None = None,
    provenance: FairnessAuditProvenance | None = None,
) -> FairnessAudit:
    """Build a deterministic audit that cannot affect agent behavior."""

    applied_policy = policy or FairnessAuditPolicy()
    selected_attributes = _attributes(demographics, attributes)
    rows = _rows(demographics)
    limitations = (
        (
            "This is descriptive post-hoc monitoring, not a fair/unfair or legal "
            "determination."
        ),
        "Demographics do not enter detection, investigation, or action selection.",
        "A household identifier may represent multiple people.",
        "Missing demographic rows and values remain visible as UNKNOWN.",
        "The observational retailer sample is not assumed to be representative.",
        "Attributes are assessed separately; intersections are not published.",
        "Review thresholds are heuristics, not statistical significance tests.",
    )
    if not selected_attributes:
        return FairnessAudit(
            availability="unavailable",
            policy=applied_policy,
            observed_household_count=len(memberships.observed),
            demographic_source_row_count=len(demographics),
            attributes=(),
            provenance=provenance,
            limitations=(
                *limitations,
                "No supported demographic attributes are available.",
            ),
        )
    stage_memberships = _stages(memberships)
    results: list[AttributeAudit] = []
    for attribute in selected_attributes:
        assignments: dict[str, str] = {}
        missing_rows = missing_values = 0
        for identifier in memberships.observed:
            row = rows.get(identifier)
            if row is None:
                assignments[identifier] = UNKNOWN_GROUP
                missing_rows += 1
            else:
                assignments[identifier] = _value(row.get(attribute))
                missing_values += assignments[identifier] == UNKNOWN_GROUP
        observed = len(assignments)
        unknown = missing_rows + missing_values
        known = observed - unknown
        coverage_suppressed = any(
            0 < count < applied_policy.minimum_group_size
            for count in (known, unknown, missing_rows, missing_values)
        )
        group_counts = Counter(assignments.values())
        assignments = {
            identifier: (
                SUPPRESSED_GROUP
                if value != UNKNOWN_GROUP
                and group_counts[value] < applied_policy.minimum_group_size
                else value
            )
            for identifier, value in assignments.items()
        }
        results.append(
            AttributeAudit(
                attribute=attribute,
                observed_count=observed,
                coverage_status=(
                    "insufficient_sample" if coverage_suppressed else "available"
                ),
                known_value_count=None if coverage_suppressed else known,
                unknown_value_count=None if coverage_suppressed else unknown,
                missing_source_row_count=(
                    None if coverage_suppressed else missing_rows
                ),
                missing_field_value_count=(
                    None if coverage_suppressed else missing_values
                ),
                coverage_rate=(
                    None
                    if coverage_suppressed
                    else known / observed
                    if observed
                    else 0.0
                ),
                stages=tuple(
                    _stage_audit(stage, assignments, applied_policy)
                    for stage in stage_memberships
                ),
            )
        )
    partial = any(
        stage.availability == "unavailable"
        for result in results
        for stage in result.stages
    )
    return FairnessAudit(
        availability="partial" if partial else "full",
        policy=applied_policy,
        observed_household_count=len(memberships.observed),
        demographic_source_row_count=len(demographics),
        attributes=tuple(results),
        provenance=provenance,
        limitations=limitations,
    )
