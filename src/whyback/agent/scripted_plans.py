"""Clearly labeled deterministic control plans for demos and offline review."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from whyback.agent.actions import ActionId
from whyback.agent.runner import make_tool_call_id
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishDecision,
    FinishProposal,
    ModelDecision,
    ToolDecision,
)
from whyback.methodology import ClaimType
from whyback.tools.contracts import ToolName


class ScriptedPlan(StrEnum):
    STANDARD = "standard"
    TYPE_A_PARTIAL = "type-a-partial"
    PROMOTION_TIMEOUT = "promotion-timeout"


def _tool(name: ToolName, household_id: str) -> ToolDecision:
    questions = {
        ToolName.CUSTOMER_TREND: "Is the decline primarily frequency or value related?",
        ToolName.CATEGORY_DECOMPOSITION: (
            "Which recorded categories contribute to lost retailer sales value?"
        ),
        ToolName.BASKET_BEHAVIOR: "Did basket size, cadence, or store behavior change?",
        ToolName.PROMOTION_RESPONSE: (
            "Did promotion-associated purchasing change across the windows?"
        ),
        ToolName.COUPON_CAMPAIGN_HISTORY: (
            "What campaign and coupon information is known or unavailable?"
        ),
        ToolName.PEER_COMPARISON: (
            "How unusual is the decline among behaviorally similar households?"
        ),
    }
    return ToolDecision(
        investigation_question=questions[name],
        selected_tool=name,
        arguments={"household_id": household_id},
        decision_summary=f"Inspect {name.value} deterministic evidence.",
    )


def _evidence_id(run_id: UUID, call_index: int, name: ToolName, ordinal: int) -> str:
    return f"ev_{make_tool_call_id(run_id, call_index, name)}_{ordinal:03d}"


def _supported_finish(
    *,
    trend_id: str,
    basket_id: str,
    counterevidence_ids: tuple[str, ...] = (),
) -> FinishDecision:
    supporting = (trend_id, basket_id)
    return FinishDecision(
        investigation_question="Is the available evidence sufficient to finish?",
        decision_summary="Submit a cadence hypothesis for deterministic review.",
        final=FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary=(
                        "Reduced recorded visit cadence is a plausible engagement "
                        "decline driver."
                    ),
                    claim_type=ClaimType.ASSOCIATIONAL,
                    supporting_evidence_ids=supporting,
                    counterevidence_ids=counterevidence_ids,
                    no_material_counterevidence_reason=(
                        None
                        if counterevidence_ids
                        else "No material counterevidence was identified in this plan."
                    ),
                    limitations=(
                        "Observed retailer behavior does not establish customer intent "
                        "or causality.",
                    ),
                ),
            ),
            proposed_confidence=ConfidenceLevel.HIGH,
            supporting_evidence_ids=supporting,
            counterevidence_ids=counterevidence_ids,
            next_best_action_id=ActionId.VISIT_FREQUENCY_REACTIVATION,
            rationale=(
                "Distinct trend and basket measures support a human-reviewed cadence "
                "test while the underlying reason remains unobserved."
            ),
            alternative_explanations=(
                "The household may have shifted activity outside the recorded "
                "retailer.",
                "The observed window may include temporary life changes or broad "
                "contemporaneous movement.",
            ),
            uncertainties=(
                "The dataset contains behavior rather than stated customer intent.",
            ),
        ),
    )


def _insufficient_finish() -> FinishDecision:
    return FinishDecision(
        investigation_question="Can any catalog action be supported safely?",
        decision_summary="Use the governed no-action fallback.",
        final=FinishProposal(
            driver_summary=(),
            proposed_confidence=ConfidenceLevel.LOW,
            supporting_evidence_ids=(),
            counterevidence_ids=(),
            next_best_action_id=ActionId.INSUFFICIENT_EVIDENCE,
            rationale="Available evidence does not support a customer action.",
            alternative_explanations=(
                "The observed decline may reflect behavior outside recorded data.",
            ),
            uncertainties=("Additional valid evidence is required.",),
        ),
    )


def build_scripted_plan(
    *,
    plan: ScriptedPlan,
    run_id: UUID,
    household_id: str,
) -> tuple[ModelDecision, ...]:
    """Build a replayable control path; this is never labeled as a live model run."""

    if plan is ScriptedPlan.STANDARD:
        trend_call = 1
        basket_call = 3
        peer_call = 4
        decisions: list[ModelDecision] = [
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _tool(ToolName.CATEGORY_DECOMPOSITION, household_id),
            _tool(ToolName.BASKET_BEHAVIOR, household_id),
            _tool(ToolName.PEER_COMPARISON, household_id),
        ]
    elif plan is ScriptedPlan.TYPE_A_PARTIAL:
        trend_call = 2
        basket_call = 3
        peer_call = 4
        decisions = [
            _tool(ToolName.COUPON_CAMPAIGN_HISTORY, household_id),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _tool(ToolName.BASKET_BEHAVIOR, household_id),
            _tool(ToolName.PEER_COMPARISON, household_id),
        ]
    else:
        # The injected promotion call consumes two execution attempts before the
        # independent analytical calls. Both timeout modes use the same call indexes.
        trend_call = 3
        basket_call = 4
        peer_call = 5
        decisions = [
            _tool(ToolName.PROMOTION_RESPONSE, household_id),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _tool(ToolName.BASKET_BEHAVIOR, household_id),
            _tool(ToolName.PEER_COMPARISON, household_id),
        ]

    counterevidence = (_evidence_id(run_id, peer_call, ToolName.PEER_COMPARISON, 17),)

    decisions.append(
        _supported_finish(
            trend_id=_evidence_id(run_id, trend_call, ToolName.CUSTOMER_TREND, 2),
            basket_id=_evidence_id(run_id, basket_call, ToolName.BASKET_BEHAVIOR, 1),
            counterevidence_ids=counterevidence,
        )
    )
    decisions.append(_insufficient_finish())
    return tuple(decisions)
