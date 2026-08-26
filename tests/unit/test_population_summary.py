"""Regression tests for deterministic population aggregation."""

from __future__ import annotations

from whyback.detection.decline import DeclineSnapshot
from whyback.reporting.population import _distribution, _edges


def _snapshot(household_id: str, baseline_value: float) -> DeclineSnapshot:
    """Build the smallest valid detector row needed by a distribution test."""

    return DeclineSnapshot(
        household_id=household_id,
        baseline_start_week=38,
        baseline_end_week=45,
        recent_start_week=46,
        recent_end_week=53,
        baseline_retailer_sales_value=baseline_value,
        recent_retailer_sales_value=0.0,
        baseline_distinct_baskets=8,
        recent_distinct_baskets=0,
        baseline_active_weeks=8,
        recent_active_weeks=0,
        sales_drop=1.0,
        trip_drop=1.0,
        active_week_drop=1.0,
        decline_score=1.0,
        eligible=True,
        flagged=True,
    )


def test_log_histogram_includes_a_maximum_rounded_above_its_generated_edge() -> None:
    """Keep every household when exp/log round the final value bin downward."""

    maximum = 3866.1800000000007
    snapshots = (_snapshot("1", 10.0), _snapshot("2", maximum))
    edges = _edges(
        [item.baseline_retailer_sales_value for item in snapshots],
        "baseline_retailer_sales_value",
    )
    distribution = _distribution(
        snapshots,
        "baseline_retailer_sales_value",
        edges,
    )

    assert edges[-1] > maximum
    assert sum(item.count for item in distribution.histogram) == len(snapshots)
