"""Max-week anchored, explainable decline scoring."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from whyback.config import DetectionConfig


class InsufficientWindowError(ValueError):
    """The observed data cannot support non-overlapping baseline/recent windows."""


class AggregateRepository(Protocol):
    """Narrow query boundary required by the detector."""

    def query(self, sql: str, parameters: list[object] | None = None) -> pd.DataFrame:
        """Execute an aggregate query and return its tabular result."""

        ...

    def scalar(self, sql: str, parameters: list[object] | None = None) -> object:
        """Execute an aggregate query expected to return one scalar value."""

        ...


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Inclusive, non-overlapping baseline and recent week ranges."""

    baseline_start: int
    baseline_end: int
    recent_start: int
    recent_end: int

    @classmethod
    def from_max_week(
        cls, max_week: int, *, baseline_weeks: int = 8, recent_weeks: int = 8
    ) -> WindowSpec:
        """Build adjacent baseline and recent windows ending at the latest week."""

        if baseline_weeks < 1 or recent_weeks < 1:
            raise ValueError("Window lengths must be positive")
        if max_week < baseline_weeks + recent_weeks:
            raise InsufficientWindowError(
                f"Need at least {baseline_weeks + recent_weeks} observed weeks; "
                f"maximum week is {max_week}"
            )
        recent_start = max_week - recent_weeks + 1
        baseline_end = recent_start - 1
        return cls(
            baseline_start=baseline_end - baseline_weeks + 1,
            baseline_end=baseline_end,
            recent_start=recent_start,
            recent_end=max_week,
        )

    def model_dump(self) -> dict[str, int]:
        """Return the four inclusive window bounds as a plain dictionary."""

        return {
            "baseline_start": self.baseline_start,
            "baseline_end": self.baseline_end,
            "recent_start": self.recent_start,
            "recent_end": self.recent_end,
        }


class DeclineSnapshot(BaseModel):
    """A detector result; explicitly a heuristic score, not a probability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    household_id: str
    baseline_start_week: int
    baseline_end_week: int
    recent_start_week: int
    recent_end_week: int
    baseline_retailer_sales_value: float
    recent_retailer_sales_value: float
    baseline_distinct_baskets: int
    recent_distinct_baskets: int
    baseline_active_weeks: int
    recent_active_weeks: int
    sales_drop: float = Field(ge=0.0, le=1.0)
    trip_drop: float = Field(ge=0.0, le=1.0)
    active_week_drop: float = Field(ge=0.0, le=1.0)
    decline_score: float = Field(ge=0.0, le=1.0)
    eligible: bool
    flagged: bool
    partial_week_limitation: str | None = None


class SensitivityRow(BaseModel):
    """Candidate count under one predeclared score threshold."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)
    eligible_households: int = Field(ge=0)
    flagged_households: int = Field(ge=0)
    flagged_share: float = Field(ge=0.0, le=1.0)


def clipped_drop(baseline: float, recent: float) -> float:
    """Return a decline fraction in [0, 1], requiring a positive baseline."""

    if baseline <= 0:
        raise ValueError("A decline ratio requires a positive baseline")
    return min(1.0, max(0.0, (baseline - recent) / baseline))


def calculate_decline_score(
    *,
    baseline_sales: float,
    recent_sales: float,
    baseline_trips: int,
    recent_trips: int,
    baseline_active_weeks: int,
    recent_active_weeks: int,
) -> tuple[float, float, float, float]:
    """Calculate the published weighted score entirely in deterministic code."""

    sales_drop = clipped_drop(baseline_sales, recent_sales)
    trip_drop = clipped_drop(float(baseline_trips), float(recent_trips))
    active_week_drop = clipped_drop(
        float(baseline_active_weeks), float(recent_active_weeks)
    )
    score = 0.50 * sales_drop + 0.30 * trip_drop + 0.20 * active_week_drop
    return sales_drop, trip_drop, active_week_drop, min(1.0, max(0.0, score))


def _identifier_sort_key(identifier: str) -> tuple[int, int | str]:
    """Sort numeric household IDs numerically before nonnumeric identifiers."""

    if identifier.isdigit():
        return (0, int(identifier))
    return (1, identifier)


def _aggregate_households(
    repository: AggregateRepository, window: WindowSpec
) -> pd.DataFrame:
    """Aggregate sales, trips, and active weeks for both detector windows."""

    return repository.query(
        """
        SELECT household_id,
               COALESCE(SUM(retailer_sales_value)
                   FILTER (WHERE week BETWEEN ? AND ?), 0)::DOUBLE
                   AS baseline_sales,
               COALESCE(SUM(retailer_sales_value)
                   FILTER (WHERE week BETWEEN ? AND ?), 0)::DOUBLE
                   AS recent_sales,
               COALESCE(SUM(distinct_baskets)
                   FILTER (WHERE week BETWEEN ? AND ?), 0)::BIGINT
                   AS baseline_trips,
               COALESCE(SUM(distinct_baskets)
                   FILTER (WHERE week BETWEEN ? AND ?), 0)::BIGINT
                   AS recent_trips,
               COUNT(DISTINCT week)
                   FILTER (WHERE week BETWEEN ? AND ?)::BIGINT
                   AS baseline_active_weeks,
               COUNT(DISTINCT week)
                   FILTER (WHERE week BETWEEN ? AND ?)::BIGINT
                   AS recent_active_weeks
        FROM household_week
        WHERE week BETWEEN ? AND ?
        GROUP BY household_id
        """,
        [
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.recent_end,
        ],
    )


def detect_declines(
    repository: AggregateRepository,
    config: DetectionConfig | None = None,
    *,
    baseline_weeks: int = 8,
    recent_weeks: int = 8,
    threshold: float | None = None,
) -> list[DeclineSnapshot]:
    """Return eligible households ranked by decline score and stable ID order."""

    policy = config or DetectionConfig()
    applied_threshold = policy.decline_threshold if threshold is None else threshold
    if not 0 <= applied_threshold <= 1:
        raise ValueError("Decline threshold must be within [0, 1]")
    max_week_value = repository.scalar("SELECT MAX(week) FROM household_week")
    if max_week_value is None:
        raise InsufficientWindowError("household_week is empty")
    max_week = int(cast(Any, max_week_value))
    window = WindowSpec.from_max_week(
        max_week, baseline_weeks=baseline_weeks, recent_weeks=recent_weeks
    )
    aggregates = _aggregate_households(repository, window)
    snapshots: list[DeclineSnapshot] = []
    limitation = (
        "Source week 53 contains fewer calendar days than an ordinary week."
        if window.recent_end == 53
        else None
    )
    records = cast(list[dict[str, Any]], aggregates.to_dict(orient="records"))
    for row in records:
        baseline_sales = float(row["baseline_sales"])
        baseline_trips = int(row["baseline_trips"])
        baseline_active_weeks = int(row["baseline_active_weeks"])
        eligible = (
            baseline_active_weeks >= policy.minimum_baseline_active_weeks
            and baseline_trips >= policy.minimum_baseline_distinct_baskets
            and baseline_sales > policy.minimum_baseline_retailer_sales_value
        )
        if not eligible:
            continue
        sales_drop, trip_drop, week_drop, score = calculate_decline_score(
            baseline_sales=baseline_sales,
            recent_sales=float(row["recent_sales"]),
            baseline_trips=baseline_trips,
            recent_trips=int(row["recent_trips"]),
            baseline_active_weeks=baseline_active_weeks,
            recent_active_weeks=int(row["recent_active_weeks"]),
        )
        snapshots.append(
            DeclineSnapshot(
                household_id=str(row["household_id"]),
                baseline_start_week=window.baseline_start,
                baseline_end_week=window.baseline_end,
                recent_start_week=window.recent_start,
                recent_end_week=window.recent_end,
                baseline_retailer_sales_value=baseline_sales,
                recent_retailer_sales_value=float(row["recent_sales"]),
                baseline_distinct_baskets=baseline_trips,
                recent_distinct_baskets=int(row["recent_trips"]),
                baseline_active_weeks=baseline_active_weeks,
                recent_active_weeks=int(row["recent_active_weeks"]),
                sales_drop=sales_drop,
                trip_drop=trip_drop,
                active_week_drop=week_drop,
                decline_score=score,
                eligible=True,
                flagged=score >= applied_threshold,
                partial_week_limitation=limitation,
            )
        )
    snapshots.sort(
        key=lambda item: (-item.decline_score, _identifier_sort_key(item.household_id))
    )
    return snapshots


def sensitivity_diagnostics(
    candidates: Iterable[DeclineSnapshot], thresholds: Iterable[float]
) -> list[SensitivityRow]:
    """Apply predeclared thresholds to the same eligible population."""

    population = list(candidates)
    total = len(population)
    rows: list[SensitivityRow] = []
    for threshold in thresholds:
        if not 0 <= threshold <= 1:
            raise ValueError("Sensitivity thresholds must be within [0, 1]")
        flagged = sum(item.decline_score >= threshold for item in population)
        rows.append(
            SensitivityRow(
                threshold=threshold,
                eligible_households=total,
                flagged_households=flagged,
                flagged_share=flagged / total if total else 0.0,
            )
        )
    return rows


def candidates_frame(candidates: Iterable[BaseModel]) -> pd.DataFrame:
    """Return a stable tabular boundary suitable for CSV artifacts."""

    return pd.DataFrame([candidate.model_dump() for candidate in candidates])
