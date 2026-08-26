"""Tests for WhyBack's demo limits behavior."""

from __future__ import annotations

import pytest

from whyback.demo_limits import (
    DEFAULT_DEMO_CUSTOMERS,
    DEFAULT_DEMO_DECLINE_THRESHOLD,
    DEMO_DECLINE_THRESHOLDS,
    MAX_DEMO_CUSTOMERS,
    MIN_DEMO_CUSTOMERS,
    validate_demo_customer_count,
    validate_demo_decline_threshold,
)


def test_demo_customer_limits_cover_the_full_synthetic_population() -> None:
    """Verify that demo customer limits cover the full synthetic population."""

    assert MIN_DEMO_CUSTOMERS == 3
    assert DEFAULT_DEMO_CUSTOMERS == 5
    assert MAX_DEMO_CUSTOMERS == 24


@pytest.mark.parametrize("customers", [MIN_DEMO_CUSTOMERS, MAX_DEMO_CUSTOMERS])
def test_demo_customer_limit_accepts_inclusive_boundaries(customers: int) -> None:
    """Verify that demo customer limit accepts inclusive boundaries."""

    validate_demo_customer_count(customers)


@pytest.mark.parametrize(
    "customers",
    [
        MIN_DEMO_CUSTOMERS - 1,
        MAX_DEMO_CUSTOMERS + 1,
        True,
        5.5,
    ],
)
def test_demo_customer_limit_rejects_values_outside_boundaries(
    customers: object,
) -> None:
    """Verify that demo customer limit rejects values outside boundaries."""

    with pytest.raises(ValueError, match="between 3 and 24"):
        validate_demo_customer_count(customers)


def test_demo_decline_threshold_accepts_only_declared_choices() -> None:
    """Verify that live runs use one of three explicit detector postures."""

    assert DEFAULT_DEMO_DECLINE_THRESHOLD == 0.3
    assert DEMO_DECLINE_THRESHOLDS == (0.2, 0.3, 0.4)
    for threshold in DEMO_DECLINE_THRESHOLDS:
        validate_demo_decline_threshold(threshold)

    for threshold in (0.0, 0.25, 1.0, True, "0.3"):
        with pytest.raises(ValueError, match=r"0\.2, 0\.3, or 0\.4"):
            validate_demo_decline_threshold(threshold)
