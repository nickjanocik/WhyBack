from __future__ import annotations

import os

import pytest

from whyback.agent.openai_backend import OpenAIResponsesBackend
from whyback.agent.state import InvestigationState
from whyback.detection.decline import DeclineSnapshot
from whyback.tools.registry import build_tool_registry

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is absent; live Responses execution was not attempted.",
)
def test_openai_backend_returns_one_strict_investigation_decision() -> None:
    snapshot = DeclineSnapshot(
        household_id="live-contract-smoke",
        baseline_start_week=38,
        baseline_end_week=45,
        recent_start_week=46,
        recent_end_week=53,
        baseline_retailer_sales_value=100.0,
        recent_retailer_sales_value=50.0,
        baseline_distinct_baskets=8,
        recent_distinct_baskets=4,
        baseline_active_weeks=8,
        recent_active_weeks=4,
        sales_drop=0.5,
        trip_drop=0.5,
        active_week_drop=0.5,
        decline_score=0.5,
        eligible=True,
        flagged=True,
    )
    state = InvestigationState.start(snapshot)
    registry = build_tool_registry()
    backend = OpenAIResponsesBackend(timeout_seconds=60.0)

    result = backend.decide_next_step(state, registry.definitions())

    assert result.provider_call_id
    assert result.model == backend.model_name
    assert result.decision.kind in {"tool", "finish"}
