"""Typed methodology policy for population context and claim boundaries."""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClaimType(StrEnum):
    """Strength of an interpretation supported by analytical evidence."""

    DESCRIPTIVE = "descriptive"
    ASSOCIATIONAL = "associational"
    CAUSAL = "causal"


class ContextClassification(StrEnum):
    """Deterministic relationship between target and contemporaneous changes."""

    CUSTOMER_SPECIFIC = "customer_specific"
    MIXED = "mixed"
    BROAD_CONTEXT = "broad_context"
    INSUFFICIENT_CONTEXT = "insufficient_context"


_CONSERVATIVE_CONTEXT_PRECEDENCE = (
    ContextClassification.BROAD_CONTEXT,
    ContextClassification.INSUFFICIENT_CONTEXT,
    ContextClassification.MIXED,
    ContextClassification.CUSTOMER_SPECIFIC,
)


def resolve_context_classifications(
    classifications: tuple[ContextClassification, ...],
) -> ContextClassification:
    """Resolve multiple bounded context calls with conservative precedence."""

    if not classifications:
        return ContextClassification.INSUFFICIENT_CONTEXT
    return next(
        item for item in _CONSERVATIVE_CONTEXT_PRECEDENCE if item in classifications
    )


class ContextPolicy(BaseModel):
    """Central, immutable thresholds for contemporaneous comparison context."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    minimum_baseline_active_weeks: int = Field(default=4, ge=1)
    minimum_baseline_distinct_baskets: int = Field(default=6, ge=1)
    minimum_baseline_retailer_sales_value: float = Field(default=0.0, ge=0.0)
    minimum_population_households: int = Field(default=20, ge=1)
    minimum_peer_households: int = Field(default=5, ge=1)
    minimum_category_households: int = Field(default=20, ge=1)
    meaningful_category_baseline_retailer_sales_value: float = Field(
        default=1.0,
        gt=0.0,
    )
    broad_declining_share: float = Field(default=0.60, ge=0.0, le=1.0)
    material_change_gap: float = Field(default=0.10, gt=0.0, le=1.0)
    similarity_tolerance: float = Field(default=0.10, ge=0.0, le=1.0)


def classify_context(
    *,
    target_change: float | None,
    population_median_change: float | None,
    population_declining_share: float | None,
    peer_median_change: float | None,
    peer_declining_share: float | None,
    population_count: int,
    peer_count: int,
    policy: ContextPolicy | None = None,
) -> ContextClassification:
    """Classify signed change context; lower change always means worse movement."""

    applied = policy or ContextPolicy()
    values = (
        target_change,
        population_median_change,
        population_declining_share,
        peer_median_change,
        peer_declining_share,
    )
    if (
        population_count < applied.minimum_population_households
        or peer_count < applied.minimum_peer_households
        or any(value is None or not math.isfinite(value) for value in values)
    ):
        return ContextClassification.INSUFFICIENT_CONTEXT

    assert target_change is not None
    assert population_median_change is not None
    assert population_declining_share is not None
    assert peer_median_change is not None
    assert peer_declining_share is not None
    if not 0.0 <= population_declining_share <= 1.0:
        raise ValueError("population_declining_share must be within [0, 1]")
    if not 0.0 <= peer_declining_share <= 1.0:
        raise ValueError("peer_declining_share must be within [0, 1]")

    population_gap = target_change - population_median_change
    peer_gap = target_change - peer_median_change
    any_broad_movement = (
        population_declining_share >= applied.broad_declining_share
        or peer_declining_share >= applied.broad_declining_share
    )
    if (
        population_gap <= -applied.material_change_gap
        and peer_gap <= -applied.material_change_gap
    ):
        return (
            ContextClassification.MIXED
            if any_broad_movement
            else ContextClassification.CUSTOMER_SPECIFIC
        )

    broad_movement = (
        population_declining_share >= applied.broad_declining_share
        and peer_declining_share >= applied.broad_declining_share
    )
    similar_to_both = (
        abs(population_gap) <= applied.similarity_tolerance
        and abs(peer_gap) <= applied.similarity_tolerance
    )
    if broad_movement and similar_to_both:
        return ContextClassification.BROAD_CONTEXT
    return ContextClassification.MIXED
