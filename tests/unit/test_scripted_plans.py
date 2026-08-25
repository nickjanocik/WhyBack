from __future__ import annotations

from uuid import UUID

import pytest

from whyback.agent.runner import make_tool_call_id
from whyback.agent.scripted_plans import ScriptedPlan, build_scripted_plan
from whyback.agent.state import FinishDecision, ToolDecision
from whyback.tools.contracts import ToolName

RUN_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_tool_call_id_is_stable_and_one_indexed() -> None:
    assert make_tool_call_id(RUN_ID, 2, ToolName.BASKET_BEHAVIOR) == (
        "call-1234567812-02-basket_behavior"
    )
    with pytest.raises(ValueError, match="start at one"):
        make_tool_call_id(RUN_ID, 0, ToolName.CUSTOMER_TREND)


@pytest.mark.parametrize(
    ("plan", "expected_tools"),
    [
        (
            ScriptedPlan.STANDARD,
            [
                ToolName.CUSTOMER_TREND,
                ToolName.CATEGORY_DECOMPOSITION,
                ToolName.BASKET_BEHAVIOR,
            ],
        ),
        (
            ScriptedPlan.TYPE_A_PARTIAL,
            [
                ToolName.COUPON_CAMPAIGN_HISTORY,
                ToolName.CUSTOMER_TREND,
                ToolName.BASKET_BEHAVIOR,
            ],
        ),
        (
            ScriptedPlan.PROMOTION_TIMEOUT,
            [
                ToolName.PROMOTION_RESPONSE,
                ToolName.CUSTOMER_TREND,
                ToolName.BASKET_BEHAVIOR,
            ],
        ),
    ],
)
def test_scripted_plans_are_explicit_and_end_with_safe_repair(
    plan: ScriptedPlan, expected_tools: list[ToolName]
) -> None:
    decisions = build_scripted_plan(
        plan=plan,
        run_id=RUN_ID,
        household_id="181",
    )

    tools = [item.selected_tool for item in decisions if isinstance(item, ToolDecision)]
    finishes = [item for item in decisions if isinstance(item, FinishDecision)]
    assert tools == expected_tools
    assert len(finishes) == 2
    assert finishes[-1].final.next_best_action_id == "INSUFFICIENT_EVIDENCE"
    assert all(
        item.arguments["household_id"] == "181"
        for item in decisions
        if isinstance(item, ToolDecision)
    )
