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
from whyback.agent.gemini_backend import GeminiFunctionCallingBackend
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


class _FakeInteractions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        return self.response


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.interactions = _FakeInteractions(response)


def _response(name: str, arguments: object) -> SimpleNamespace:
    call = SimpleNamespace(
        type="function_call",
        name=name,
        arguments=arguments,
        id="call-1",
    )
    usage = SimpleNamespace(
        total_input_tokens=22,
        total_output_tokens=10,
        total_thought_tokens=3,
        total_tool_use_tokens=2,
        total_tokens=35,
    )
    return SimpleNamespace(
        id="v1_gemini-interaction-1",
        status="requires_action",
        steps=[call],
        usage=usage,
    )


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


def test_gemini_backend_sends_one_strict_function_decision() -> None:
    response = _response(
        "customer_trend",
        {
            "investigation_question": "Did trip frequency fall?",
            "decision_summary": "Inspect frequency and value trajectory.",
            "arguments": {"household_id": "42"},
        },
    )
    client = _FakeClient(response)
    backend = GeminiFunctionCallingBackend(
        client=client,
        model="gemini-3.7-flash",
        thinking_level="high",
    )

    result = backend.decide_next_step(_state(), ToolRegistry().definitions())

    assert result.decision == _tool_decision()
    assert result.provider_call_id == "v1_gemini-interaction-1"
    assert result.usage.input_tokens == 22
    assert result.usage.output_tokens == 10
    assert result.usage.total_tokens == 35
    request = client.interactions.kwargs
    assert request["model"] == "gemini-3.7-flash"
    assert request["store"] is False
    assert request["stream"] is False
    assert request["api_version"] == "v1"
    assert request["timeout"] == 60.0
    assert "previous_interaction_id" not in request
    request_input = __import__("json").loads(request["input"])
    assert {item["action_id"] for item in request_input["action_catalog"]} == {
        item.value for item in ActionId
    }
    assert set(request_input) == {"action_catalog", "repair_issues", "state"}
    config = request["generation_config"]
    assert config.max_output_tokens == 1200
    assert config.thinking_level == "high"
    assert config.thinking_summaries == "none"
    function_config = config.tool_choice.allowed_tools
    assert function_config.mode == "any"
    functions = request["tools"]
    assert set(function_config.tools) == {item.name for item in functions}
    assert len(functions) == 7
    category = next(item for item in functions if item.name == "category_decomposition")
    nested = category.parameters["properties"]["arguments"]
    assert nested["additionalProperties"] is False
    assert set(nested["required"]) == {"household_id", "top_n"}
    finish = next(item for item in functions if item.name == "finish_investigation")
    serialized_finish_schema = __import__("json").dumps(finish.parameters)
    assert '"$defs"' not in serialized_finish_schema
    assert '"$ref"' not in serialized_finish_schema


def test_gemini_backend_parses_finish_action() -> None:
    payload = {
        "investigation_question": _finish_decision().investigation_question,
        "decision_summary": _finish_decision().decision_summary,
        "final": _finish_decision().final.model_dump(mode="json"),
    }
    client = _FakeClient(_response("finish_investigation", payload))
    backend = GeminiFunctionCallingBackend(client=client)

    result = backend.decide_next_step(_state(), ())

    assert result.decision == _finish_decision()
    declarations = client.interactions.kwargs["tools"]
    assert len(declarations) == 1


def test_gemini_backend_uses_function_call_id_for_stateless_response() -> None:
    response = _response(
        "customer_trend",
        {
            "investigation_question": "Did trip frequency fall?",
            "decision_summary": "Inspect frequency and value trajectory.",
            "arguments": {"household_id": "42"},
        },
    )
    response.id = None
    response.steps[0].id = "gemini-function-call-1"
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    result = backend.decide_next_step(_state(), ToolRegistry().definitions())

    assert result.provider_call_id == "gemini-function-call-1"


def test_gemini_backend_rejects_multiple_function_calls() -> None:
    response = _response("customer_trend", {})
    response.steps.append(response.steps[0])
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="exactly one"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_gemini_backend_rejects_unoffered_function() -> None:
    response = _response(
        "customer_trend",
        {
            "investigation_question": "Did trip frequency fall?",
            "decision_summary": "Inspect the trajectory.",
            "arguments": {"household_id": "42"},
        },
    )
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="not offered"):
        backend.decide_next_step(_state(), ())


def test_gemini_backend_rejects_incomplete_response() -> None:
    response = _response("customer_trend", {})
    response.status = "incomplete"
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="require action"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda response: setattr(response, "steps", None), "not a sequence"),
        (
            lambda response: setattr(
                response.usage, "total_input_tokens", "not-an-int"
            ),
            "invalid token",
        ),
        (
            lambda response: (
                setattr(response, "id", None),
                setattr(response.steps[0], "id", None),
            ),
            "interaction or function-call ID",
        ),
        (
            lambda response: setattr(response, "errors", [object()]),
            "provider errors",
        ),
        (
            lambda response: setattr(response.usage, "total_tokens", 1),
            "did not reconcile",
        ),
    ),
)
def test_gemini_backend_wraps_malformed_provider_metadata(
    mutation: Any, message: str
) -> None:
    response = _response(
        "customer_trend",
        {
            "investigation_question": "Inspect?",
            "decision_summary": "Inspect.",
            "arguments": {"household_id": "42"},
        },
    )
    mutation(response)
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match=message):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_gemini_backend_rejects_arguments_outside_the_offered_schema() -> None:
    response = _response(
        "customer_trend",
        {
            "investigation_question": "Inspect?",
            "decision_summary": "Inspect.",
            "arguments": {"household_id": "42", "thought_process": "private"},
        },
    )
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="offered schema"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_gemini_backend_does_not_echo_invalid_provider_payload() -> None:
    private_content = "synthetic-private-content"
    response = _response(
        "customer_trend",
        {
            "investigation_question": "Inspect?",
            "decision_summary": "Inspect.",
            "arguments": {"household_id": "42"},
            "thought_process": private_content,
        },
    )
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse) as caught:
        backend.decide_next_step(_state(), ToolRegistry().definitions())

    assert str(caught.value) == "Invalid function call payload"
    assert private_content not in str(caught.value)


def test_gemini_backend_sanitizes_provider_request_errors() -> None:
    sensitive_marker = "synthetic-sensitive-provider-marker"

    class _RaisingInteractions:
        def create(self, **kwargs: Any) -> object:
            del kwargs
            raise RuntimeError(f"provider rejected {sensitive_marker}")

    client = SimpleNamespace(interactions=_RaisingInteractions())
    backend = GeminiFunctionCallingBackend(client=client)

    with pytest.raises(ModelBackendError) as caught:
        backend.decide_next_step(_state(), ToolRegistry().definitions())

    assert str(caught.value) == "Gemini Interactions request failed"
    assert sensitive_marker not in str(caught.value)


def test_gemini_backend_requires_a_key_when_no_client_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(MissingModelCredential, match="GEMINI_API_KEY"):
        GeminiFunctionCallingBackend()


def test_gemini_backend_passes_gemini_key_explicitly_and_disables_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_client(**kwargs: Any) -> _FakeClient:
        captured.update(kwargs)
        return _FakeClient(_response("customer_trend", {}))

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "different-test-google-key")
    monkeypatch.setattr("whyback.agent.gemini_backend.genai.Client", fake_client)

    GeminiFunctionCallingBackend(timeout_seconds=12.5)

    assert captured["api_key"] == "test-gemini-key"
    http_options = captured["http_options"]
    assert http_options.api_version == "v1"
    assert http_options.timeout == 12_500
    assert http_options.retry_options.attempts == 1
