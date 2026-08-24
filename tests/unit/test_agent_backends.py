from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from whyback.agent.actions import ActionId
from whyback.agent.backend import (
    MalformedModelResponse,
    MissingModelCredential,
    ModelBackendError,
)
from whyback.agent.openai_backend import OpenAIResponsesBackend
from whyback.agent.scripted_backend import ScriptedBackend
from whyback.agent.state import (
    DriverClaim,
    FinishDecision,
    FinishProposal,
    InvestigationState,
    ToolDecision,
)
from whyback.detection.decline import DeclineSnapshot
from whyback.tools.contracts import ToolName
from whyback.tools.registry import ToolRegistry


def _snapshot() -> DeclineSnapshot:
    return DeclineSnapshot(
        household_id="42",
        baseline_start_week=38,
        baseline_end_week=45,
        recent_start_week=46,
        recent_end_week=53,
        baseline_retailer_sales_value=200.0,
        recent_retailer_sales_value=100.0,
        baseline_distinct_baskets=10,
        recent_distinct_baskets=5,
        baseline_active_weeks=8,
        recent_active_weeks=4,
        sales_drop=0.5,
        trip_drop=0.5,
        active_week_drop=0.5,
        decline_score=0.5,
        eligible=True,
        flagged=True,
        partial_week_limitation="Week 53 is partial.",
    )


def _state() -> InvestigationState:
    return InvestigationState.start(
        _snapshot(),
        run_id=UUID("00000000-0000-0000-0000-000000000042"),
    )


def _tool_decision() -> ToolDecision:
    return ToolDecision(
        investigation_question="Did trip frequency fall?",
        selected_tool=ToolName.CUSTOMER_TREND,
        arguments={"household_id": "42"},
        decision_summary="Inspect frequency and value trajectory.",
    )


def _finish_decision() -> FinishDecision:
    return FinishDecision(
        investigation_question="Is the evidence sufficient to finish?",
        decision_summary="Submit a cautious evidence-grounded conclusion.",
        final=FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary="Reduced visit frequency is a plausible driver.",
                    supporting_evidence_ids=("ev-trend",),
                ),
            ),
            proposed_confidence="medium",
            supporting_evidence_ids=("ev-trend",),
            counterevidence_ids=(),
            next_best_action_id=ActionId.VISIT_FREQUENCY_REACTIVATION,
            rationale="The recorded pattern supports a human-reviewed test.",
            alternative_explanations=(
                "Purchases may have shifted outside the retailer.",
            ),
            uncertainties=("The data contains no direct reason for the change.",),
        ),
    )


class _FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        return self.response


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.responses = _FakeResponses(response)


def _response(name: str, arguments: str) -> SimpleNamespace:
    call = SimpleNamespace(
        type="function_call",
        name=name,
        arguments=arguments,
        call_id="call-1",
    )
    usage = SimpleNamespace(input_tokens=20, output_tokens=10, total_tokens=30)
    return SimpleNamespace(id="resp-1", output=[call], usage=usage)


def test_investigation_state_is_frozen_and_budget_bounded() -> None:
    state = _state()

    assert state.window.model_dump() == {
        "baseline_start": 38,
        "baseline_end": 45,
        "recent_start": 46,
        "recent_end": 53,
    }
    assert state.compact_model_context()["household_id"] == "42"
    with pytest.raises(ValidationError):
        state.remaining_tool_budget = -1  # type: ignore[misc]
    with pytest.raises(ValueError, match="positive"):
        InvestigationState.start(_snapshot(), max_tool_executions=0)


def test_finish_proposal_rejects_duplicate_evidence_references() -> None:
    with pytest.raises(ValidationError, match="unique"):
        FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary="A plausible driver.",
                    supporting_evidence_ids=("ev-1",),
                ),
            ),
            proposed_confidence="low",
            supporting_evidence_ids=("ev-1", "ev-1"),
            counterevidence_ids=(),
            next_best_action_id=ActionId.MONITOR,
            rationale="Monitor the pattern.",
            alternative_explanations=("The observed interval may be temporary.",),
            uncertainties=("No direct reason is recorded.",),
        )


def test_scripted_backend_exposes_offered_tools_and_exhaustion() -> None:
    backend = ScriptedBackend([_tool_decision()])
    definitions = ToolRegistry().definitions((ToolName.CUSTOMER_TREND,))

    result = backend.decide_next_step(_state(), definitions)

    assert result.decision == _tool_decision()
    assert result.usage.decisions == 1
    assert backend.calls[0].allowed_tools == (ToolName.CUSTOMER_TREND,)
    with pytest.raises(ModelBackendError, match="exhausted"):
        backend.decide_next_step(_state(), definitions)


def test_scripted_backend_rejects_malformed_decision() -> None:
    backend = ScriptedBackend([{"kind": "tool", "selected_tool": "customer_trend"}])

    with pytest.raises(MalformedModelResponse, match="invalid"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_openai_backend_sends_one_strict_function_decision() -> None:
    response = _response(
        "customer_trend",
        """{"investigation_question":"Did trip frequency fall?",\
"decision_summary":"Inspect frequency and value trajectory.",\
"arguments":{"household_id":"42"}}""",
    )
    client = _FakeClient(response)
    backend = OpenAIResponsesBackend(client=client, model="gpt-5.6-sol")

    result = backend.decide_next_step(_state(), ToolRegistry().definitions())

    assert result.decision == _tool_decision()
    assert result.usage.total_tokens == 30
    request = client.responses.kwargs
    assert request["model"] == "gpt-5.6-sol"
    assert request["parallel_tool_calls"] is False
    assert request["tool_choice"] == "required"
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "medium"}
    functions = request["tools"]
    assert len(functions) == 7
    assert all(item["strict"] is True for item in functions)
    category = next(
        item for item in functions if item["name"] == "category_decomposition"
    )
    nested = category["parameters"]["properties"]["arguments"]
    assert nested["additionalProperties"] is False
    assert set(nested["required"]) == {"household_id", "top_n"}


def test_openai_backend_parses_finish_action() -> None:
    payload = {
        "investigation_question": _finish_decision().investigation_question,
        "decision_summary": _finish_decision().decision_summary,
        "final": _finish_decision().final.model_dump(mode="json"),
    }
    client = _FakeClient(
        _response("finish_investigation", __import__("json").dumps(payload))
    )
    backend = OpenAIResponsesBackend(client=client)

    result = backend.decide_next_step(_state(), ())

    assert result.decision == _finish_decision()
    assert len(client.responses.kwargs["tools"]) == 1


def test_openai_backend_rejects_multiple_function_calls() -> None:
    response = _response("customer_trend", "{}")
    response.output.append(response.output[0])
    backend = OpenAIResponsesBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="exactly one"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_openai_backend_rejects_unoffered_function() -> None:
    response = _response(
        "customer_trend",
        """{"investigation_question":"Did trip frequency fall?",\
"decision_summary":"Inspect the trajectory.",\
"arguments":{"household_id":"42"}}""",
    )
    backend = OpenAIResponsesBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="not offered"):
        backend.decide_next_step(_state(), ())


def test_openai_backend_rejects_incomplete_response() -> None:
    response = _response("customer_trend", "{}")
    response.status = "incomplete"
    backend = OpenAIResponsesBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="status"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_openai_backend_requires_a_key_when_no_client_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingModelCredential, match="OPENAI_API_KEY"):
        OpenAIResponsesBackend()
