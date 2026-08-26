"""Tests for WhyBack's fault injection behavior."""

from __future__ import annotations

from uuid import UUID

import pytest

from whyback.agent.faults import (
    DemoFaultConfigurationError,
    DemoFaultInjector,
    DemoFaultScenario,
)
from whyback.tools.contracts import AnalysisWindow, ToolExecutionContext, ToolName


def _context() -> ToolExecutionContext:
    """Create the context value used by these tests."""

    return ToolExecutionContext(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        tool_call_id="call",
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=1,
            recent_start=2,
            recent_end=2,
        ),
    )


def test_demo_fault_requires_explicit_enable_and_known_scenario() -> None:
    """Verify that demo fault requires explicit enable and known scenario."""

    with pytest.raises(DemoFaultConfigurationError, match="enabled=True"):
        DemoFaultInjector(  # type: ignore[arg-type]
            DemoFaultScenario.PROMOTION_TIMEOUT_ONCE,
            enabled=False,
        )
    with pytest.raises(DemoFaultConfigurationError, match="Unknown"):
        DemoFaultInjector.from_spec("customer_trend:explode", enabled=True)


def test_timeout_once_only_intercepts_first_promotion_attempt() -> None:
    """Verify that timeout once only intercepts first promotion attempt."""

    injector = DemoFaultInjector.from_spec(
        "promotion_response:timeout-once", enabled=True
    )

    first = injector.intercept(
        name=ToolName.PROMOTION_RESPONSE,
        attempt=1,
        context=_context(),
        normalized_parameters={"household_id": "1"},
    )
    second = injector.intercept(
        name=ToolName.PROMOTION_RESPONSE,
        attempt=2,
        context=_context(),
        normalized_parameters={"household_id": "1"},
    )
    unrelated = injector.intercept(
        name=ToolName.CUSTOMER_TREND,
        attempt=1,
        context=_context(),
        normalized_parameters={"household_id": "1"},
    )

    assert first is not None and first.retryable and first.evidence == ()
    assert first.provenance.diagnostics["demo_fault"] is True
    assert second is None
    assert unrelated is None


def test_timeout_always_intercepts_both_permitted_attempts() -> None:
    """Verify that timeout always intercepts both permitted attempts."""

    injector = DemoFaultInjector.from_spec(
        "promotion_response:timeout-always", enabled=True
    )

    results = [
        injector.intercept(
            name=ToolName.PROMOTION_RESPONSE,
            attempt=attempt,
            context=_context(),
            normalized_parameters={"household_id": "1"},
        )
        for attempt in (1, 2)
    ]

    assert all(result is not None and result.retryable for result in results)
