"""Shared customer-count limits for bounded WhyBack demo batches."""

from typing import Final

MIN_DEMO_CUSTOMERS: Final = 3
DEFAULT_DEMO_CUSTOMERS: Final = 5
MAX_DEMO_CUSTOMERS: Final = 24
DEMO_DECLINE_THRESHOLDS: Final = (0.2, 0.3, 0.4)
DEFAULT_DEMO_DECLINE_THRESHOLD: Final = 0.3


def validate_demo_customer_count(customers: object) -> None:
    """Reject demo batch sizes outside the supported inclusive range."""

    if (
        isinstance(customers, bool)
        or not isinstance(customers, int)
        or customers < MIN_DEMO_CUSTOMERS
        or customers > MAX_DEMO_CUSTOMERS
    ):
        raise ValueError(
            "Demo runs support between "
            f"{MIN_DEMO_CUSTOMERS} and {MAX_DEMO_CUSTOMERS} customers"
        )


def validate_demo_decline_threshold(decline_threshold: object) -> None:
    """Reject detector thresholds outside the dashboard's declared choices."""

    if (
        isinstance(decline_threshold, bool)
        or not isinstance(decline_threshold, (int, float))
        or float(decline_threshold) not in DEMO_DECLINE_THRESHOLDS
    ):
        raise ValueError("Demo decline threshold must be one of 0.2, 0.3, or 0.4")
