"""Strict, fail-closed Next Best Action catalog contracts and loading."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from whyback.tools.contracts import ToolName

DEFAULT_ACTION_CATALOG_PATH = Path("configs/actions.yaml")


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


class EvidencePrerequisite(BaseModel):
    """Machine-checkable evidence family required to support an action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str = Field(min_length=1)
    source_tools: tuple[ToolName, ...] = Field(min_length=1)
    metrics: tuple[str, ...] = Field(min_length=1)
    metric_match: Literal["any", "all"]
    minimum_matching_records: int = Field(ge=1)
    minimum_distinct_tools: int = Field(ge=1)

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
