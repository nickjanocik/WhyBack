"""Shared customer-count limits for bounded WhyBack demo batches."""

from typing import Final

MIN_DEMO_CUSTOMERS: Final = 5
DEFAULT_DEMO_CUSTOMERS: Final = 5
MAX_DEMO_CUSTOMERS: Final = 24


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
