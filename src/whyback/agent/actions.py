"""Strict, fail-closed Next Best Action catalog contracts and loading."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from whyback.tools.contracts import EvidenceRecord, ToolName

_PACKAGE_ACTION_CATALOG_PATH = Path(__file__).parents[1] / "resources" / "actions.yaml"
_REPOSITORY_ACTION_CATALOG_PATH = Path(__file__).parents[3] / "configs" / "actions.yaml"
DEFAULT_ACTION_CATALOG_PATH = (
    _PACKAGE_ACTION_CATALOG_PATH
    if _PACKAGE_ACTION_CATALOG_PATH.is_file()
    else _REPOSITORY_ACTION_CATALOG_PATH
)


class ActionCatalogError(ValueError):
    """Raised when the checked-in action catalog cannot be trusted."""


class ActionId(StrEnum):
    """The complete allowlist of actions that a model may select."""

    CATEGORY_WINBACK = "CATEGORY_WINBACK"
    VISIT_FREQUENCY_REACTIVATION = "VISIT_FREQUENCY_REACTIVATION"
    PROMOTION_VALUE_REENGAGEMENT = "PROMOTION_VALUE_REENGAGEMENT"
    PERSONALIZED_CHECK_IN = "PERSONALIZED_CHECK_IN"
    MONITOR = "MONITOR"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


EXPECTED_ACTION_IDS = frozenset(ActionId)


class DimensionPredicate(BaseModel):
    """A machine-checkable constraint on an evidence dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    operator: Literal["equals", "not_equals"]
    value: str = Field(min_length=1)

    def matches(self, record: EvidenceRecord) -> bool:
        observed = record.dimensions.get(self.key)
        if observed is None:
            return False
        if self.operator == "equals":
            return observed == self.value
        return observed != self.value


class EvidencePredicate(BaseModel):
    """Direction, materiality, and dimension policy for one evidence metric."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: str = Field(min_length=1)
    field: Literal["baseline_value", "recent_value", "value", "change"]
    operator: Literal["lt", "lte", "gt", "gte", "eq", "neq"]
    threshold: float
    dimensions: tuple[DimensionPredicate, ...] = ()

    def matches(self, record: EvidenceRecord) -> bool:
        if record.metric != self.metric or not all(
            item.matches(record) for item in self.dimensions
        ):
            return False
        observed = getattr(record, self.field)
        if observed is None:
            return False
        comparisons = {
            "lt": observed < self.threshold,
            "lte": observed <= self.threshold,
            "gt": observed > self.threshold,
            "gte": observed >= self.threshold,
            "eq": observed == self.threshold,
            "neq": observed != self.threshold,
        }
        return comparisons[self.operator]


class EvidencePrerequisite(BaseModel):
    """Machine-checkable evidence family required to support an action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str = Field(min_length=1)
    source_tools: tuple[ToolName, ...] = Field(min_length=1)
    metrics: tuple[str, ...] = Field(min_length=1)
    metric_match: Literal["any", "all"]
    minimum_matching_records: int = Field(ge=1)
    minimum_distinct_tools: int = Field(ge=1)
    predicates: tuple[EvidencePredicate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_rule(self) -> Self:
        if len(set(self.source_tools)) != len(self.source_tools):
            raise ValueError("Evidence prerequisite source tools must be unique")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Evidence prerequisite metrics must be unique")
        if any(not metric.strip() for metric in self.metrics):
            raise ValueError("Evidence prerequisite metrics cannot be blank")
        if self.minimum_distinct_tools > len(self.source_tools):
            raise ValueError(
                "minimum_distinct_tools cannot exceed the permitted source tools"
            )
        if self.minimum_distinct_tools > self.minimum_matching_records:
            raise ValueError(
                "minimum_distinct_tools cannot exceed minimum_matching_records"
            )
        predicate_metrics = {item.metric for item in self.predicates}
        if predicate_metrics != set(self.metrics):
            raise ValueError(
                "Every prerequisite metric must have a directional predicate and "
                "predicates cannot name other metrics"
            )
        return self


class SuccessMetric(BaseModel):
    """Recommended deterministic outcome measure for a reviewed action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    desired_direction: Literal["increase", "decrease", "maintain_or_increase"]
    evaluation_window_weeks: int = Field(ge=1, le=52)


class ExperimentPlan(BaseModel):
    """Suggested experiment or audit holdout for a reviewed recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    design: Literal["randomized_holdout", "matched_holdout", "reviewer_audit_holdout"]
    holdout_fraction: float = Field(gt=0.0, lt=1.0)
    description: str = Field(min_length=1)


class ActionDefinition(BaseModel):
    """One immutable, reviewer-facing action definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: ActionId
    description: str = Field(min_length=1)
    evidence_prerequisites: tuple[EvidencePrerequisite, ...]
    contraindications: tuple[str, ...] = ()
    human_review_required: Literal[True]
    fallback_only: bool = False
    success_metric: SuccessMetric
    experiment: ExperimentPlan

    @model_validator(mode="after")
    def validate_selection_policy(self) -> Self:
        is_insufficient = self.action_id is ActionId.INSUFFICIENT_EVIDENCE
        if self.fallback_only != is_insufficient:
            raise ValueError(
                "Only INSUFFICIENT_EVIDENCE may be marked fallback_only, and it must be"
            )
        if is_insufficient and self.evidence_prerequisites:
            raise ValueError("INSUFFICIENT_EVIDENCE cannot require supporting evidence")
        if not is_insufficient and not self.evidence_prerequisites:
            raise ValueError("Supported actions require evidence prerequisites")
        if any(not item.strip() for item in self.contraindications):
            raise ValueError("Contraindications cannot be blank")
        return self


class ActionCatalog(BaseModel):
    """The exact versioned allowlist from which the model may choose."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_version: Literal[1]
    actions: tuple[ActionDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_exact_allowlist(self) -> Self:
        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("Action IDs must be unique")
        actual = frozenset(action_ids)
        if actual != EXPECTED_ACTION_IDS:
            missing = sorted(item.value for item in EXPECTED_ACTION_IDS - actual)
            unexpected = sorted(item.value for item in actual - EXPECTED_ACTION_IDS)
            raise ValueError(
                f"Action catalog must contain the exact allowlist; missing={missing}, "
                f"unexpected={unexpected}"
            )
        return self

    @property
    def action_ids(self) -> frozenset[ActionId]:
        """Return the immutable catalog allowlist."""

        return frozenset(action.action_id for action in self.actions)

    def get(self, action_id: ActionId | str) -> ActionDefinition:
        """Resolve an allowlisted action or reject the selection."""

        try:
            normalized = ActionId(action_id)
        except ValueError as exc:
            raise ActionCatalogError(f"Unknown action ID: {action_id}") from exc
        for action in self.actions:
            if action.action_id is normalized:
                return action
        raise ActionCatalogError(f"Action is not present in the catalog: {normalized}")

    def compact_model_context(self) -> tuple[dict[str, Any], ...]:
        """Expose bounded selection policy without operational side effects."""

        return tuple(
            {
                "action_id": action.action_id.value,
                "description": action.description,
                "evidence_prerequisites": [
                    {
                        "description": rule.description,
                        "source_tools": [item.value for item in rule.source_tools],
                        "metrics": list(rule.metrics),
                        "minimum_matching_records": rule.minimum_matching_records,
                        "minimum_distinct_tools": rule.minimum_distinct_tools,
                        "predicates": [
                            predicate.model_dump(mode="json")
                            for predicate in rule.predicates
                        ],
                    }
                    for rule in action.evidence_prerequisites
                ],
                "contraindications": list(action.contraindications),
                "human_review_required": True,
                "fallback_only": action.fallback_only,
            }
            for action in self.actions
        )


def load_action_catalog(
    path: Path = DEFAULT_ACTION_CATALOG_PATH,
) -> ActionCatalog:
    """Load and strictly validate a YAML action catalog, failing closed."""

    try:
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ActionCatalogError(
            f"Unable to load action catalog at {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ActionCatalogError("Action catalog root must be a mapping")
    try:
        return ActionCatalog.model_validate(raw)
    except ValueError as exc:
        raise ActionCatalogError(f"Invalid action catalog at {path}: {exc}") from exc
