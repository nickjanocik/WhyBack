"""Tests for WhyBack's demo limits behavior."""

from __future__ import annotations

import pytest

from whyback.demo_limits import (
    DEFAULT_DEMO_CUSTOMERS,
    MAX_DEMO_CUSTOMERS,
    MIN_DEMO_CUSTOMERS,
    validate_demo_customer_count,
)


def test_demo_customer_limits_cover_the_full_synthetic_population() -> None:
    """Verify that demo customer limits cover the full synthetic population."""

    assert MIN_DEMO_CUSTOMERS == 5
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

    with pytest.raises(ValueError, match="between 5 and 24"):
        validate_demo_customer_count(customers)
