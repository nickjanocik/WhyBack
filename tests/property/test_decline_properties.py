from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from whyback.detection.decline import calculate_decline_score


@given(
    baseline_sales=st.floats(min_value=0.01, max_value=1_000_000, allow_nan=False),
    recent_sales=st.floats(min_value=-1_000_000, max_value=2_000_000, allow_nan=False),
    baseline_trips=st.integers(min_value=1, max_value=10_000),
    recent_trips=st.integers(min_value=0, max_value=20_000),
    baseline_weeks=st.integers(min_value=1, max_value=53),
    recent_weeks=st.integers(min_value=0, max_value=53),
)
def test_decline_score_is_always_bounded(
    baseline_sales: float,
    recent_sales: float,
    baseline_trips: int,
    recent_trips: int,
    baseline_weeks: int,
    recent_weeks: int,
) -> None:
    *_, score = calculate_decline_score(
        baseline_sales=baseline_sales,
        recent_sales=recent_sales,
        baseline_trips=baseline_trips,
        recent_trips=recent_trips,
        baseline_active_weeks=baseline_weeks,
        recent_active_weeks=recent_weeks,
    )

    assert 0.0 <= score <= 1.0
