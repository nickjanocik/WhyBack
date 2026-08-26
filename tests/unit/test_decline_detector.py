"""Tests for WhyBack's decline detector behavior."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from whyback.config import DetectionConfig
from whyback.data.repository import DataRepository
from whyback.detection.decline import (
    InsufficientWindowError,
    WindowSpec,
    calculate_decline_score,
    clipped_drop,
    detect_declines,
    sensitivity_diagnostics,
)


def _repository(tmp_path: Path, rows: list[dict[str, object]]) -> DataRepository:
    """Create an in-memory analytical repository for this test."""

    pd.DataFrame(rows).to_parquet(tmp_path / "household_week.parquet", index=False)
    return DataRepository(
        tmp_path,
        required_tables=("household_week",),
        validate_manifest=False,
    )


def test_window_boundaries_are_inclusive_and_nonoverlapping() -> None:
    """Verify that window boundaries are inclusive and nonoverlapping."""

    window = WindowSpec.from_max_week(53)

    assert window.baseline_start == 38
    assert window.baseline_end == 45
    assert window.recent_start == 46
    assert window.recent_end == 53


def test_too_few_observed_weeks_is_explicit() -> None:
    """Verify that too few observed weeks is explicit."""

    with pytest.raises(InsufficientWindowError, match="at least 16"):
        WindowSpec.from_max_week(15)


def test_hand_calculated_decline_score() -> None:
    """Verify that hand calculated decline score."""

    drops = calculate_decline_score(
        baseline_sales=80.0,
        recent_sales=40.0,
        baseline_trips=8,
        recent_trips=4,
        baseline_active_weeks=8,
        recent_active_weeks=4,
    )

    assert drops == (0.5, 0.5, 0.5, 0.5)


@pytest.mark.parametrize(
    ("baseline", "recent", "expected"),
    [(10.0, 20.0, 0.0), (10.0, -5.0, 1.0), (10.0, 0.0, 1.0)],
)
def test_drop_is_clipped(baseline: float, recent: float, expected: float) -> None:
    """Verify that drop is clipped."""

    assert clipped_drop(baseline, recent) == expected


def test_nonpositive_baseline_is_rejected() -> None:
    """Verify that nonpositive baseline is rejected."""

    with pytest.raises(ValueError, match="positive baseline"):
        clipped_drop(0.0, 0.0)


def test_detector_enforces_eligibility_and_stable_ranking(tmp_path: Path) -> None:
    """Verify that detector enforces eligibility and stable ranking."""

    rows: list[dict[str, object]] = []
    for week in range(38, 46):
        rows.extend(
            [
                {
                    "household_id": "10",
                    "week": week,
                    "retailer_sales_value": 10.0,
                    "units": 1.0,
                    "distinct_baskets": 1,
                    "active_days": 1,
                },
                {
                    "household_id": "2",
                    "week": week,
                    "retailer_sales_value": 10.0,
                    "units": 1.0,
                    "distinct_baskets": 1,
                    "active_days": 1,
                },
            ]
        )
    for week in range(46, 50):
        for household_id in ("10", "2"):
            rows.append(
                {
                    "household_id": household_id,
                    "week": week,
                    "retailer_sales_value": 10.0,
                    "units": 1.0,
                    "distinct_baskets": 1,
                    "active_days": 1,
                }
            )
    rows.extend(
        {
            "household_id": "ineligible",
            "week": week,
            "retailer_sales_value": 10.0,
            "units": 1.0,
            "distinct_baskets": 1,
            "active_days": 1,
        }
        for week in range(42, 46)
    )
    rows.append(
        {
            "household_id": "anchor",
            "week": 53,
            "retailer_sales_value": 1.0,
            "units": 1.0,
            "distinct_baskets": 1,
            "active_days": 1,
        }
    )

    with _repository(tmp_path, rows) as repository:
        candidates = detect_declines(repository)

    assert [candidate.household_id for candidate in candidates] == ["2", "10"]
    assert all(math.isclose(candidate.decline_score, 0.5) for candidate in candidates)
    assert all(candidate.flagged for candidate in candidates)
    assert all(candidate.partial_week_limitation for candidate in candidates)


def test_sensitivity_uses_same_eligible_population(tmp_path: Path) -> None:
    """Verify that sensitivity uses same eligible population."""

    rows = []
    for week in range(38, 46):
        rows.append(
            {
                "household_id": "1",
                "week": week,
                "retailer_sales_value": 10.0,
                "units": 1.0,
                "distinct_baskets": 1,
                "active_days": 1,
            }
        )
    rows.append(
        {
            "household_id": "anchor",
            "week": 53,
            "retailer_sales_value": 1.0,
            "units": 1.0,
            "distinct_baskets": 1,
            "active_days": 1,
        }
    )
    with _repository(tmp_path, rows) as repository:
        candidates = detect_declines(repository, DetectionConfig())
    diagnostics = sensitivity_diagnostics(candidates, (0.2, 0.3, 0.4))

    assert [row.flagged_households for row in diagnostics] == [1, 1, 1]
    assert all(row.eligible_households == 1 for row in diagnostics)
