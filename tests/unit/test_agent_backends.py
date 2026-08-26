"""Tests for WhyBack's agent backends behavior."""

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
from whyback.methodology import ClaimType
from whyback.tools.contracts import ToolDefinition, ToolName
from whyback.tools.registry import ToolRegistry


def _snapshot() -> DeclineSnapshot:
    """Create a deterministic decline snapshot for this test."""

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
    """Create an application-owned investigation state for this test."""

    return InvestigationState.start(
        _snapshot(),
        run_id=UUID("00000000-0000-0000-0000-000000000042"),
    )


def _tool_decision() -> ToolDecision:
    """Create a typed analytical-tool decision for this test."""

    return ToolDecision(
        investigation_question="Did trip frequency fall?",
        selected_tool=ToolName.CUSTOMER_TREND,
        arguments={"household_id": "42"},
        decision_summary="Inspect frequency and value trajectory.",
    )


def _finish_decision() -> FinishDecision:
    """Create a finish decision for backend contract tests."""

    return FinishDecision(
        investigation_question="Is the evidence sufficient to finish?",
        decision_summary="Submit a cautious evidence-grounded conclusion.",
        final=FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary="Reduced visit frequency is a plausible driver.",
                    claim_type=ClaimType.ASSOCIATIONAL,
                    supporting_evidence_ids=("ev-trend",),
                    no_material_counterevidence_reason=(
                        "No material counterevidence was identified."
                    ),
                    limitations=("The evidence is observational.",),
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


def _finish_payload() -> dict[str, Any]:
    """Create the flat provider payload that maps to the typed finish decision."""

    decision = _finish_decision()
    driver = decision.final.driver_summary[0]
    return {
        "investigation_question": decision.investigation_question,
        "decision_summary": decision.decision_summary,
        "driver_summary": driver.summary,
        "driver_claim_type": driver.claim_type.value,
        "supporting_evidence_ids": list(driver.supporting_evidence_ids),
        "counterevidence_ids": list(driver.counterevidence_ids),
        "counterevidence_assessment": (driver.no_material_counterevidence_reason),
        "limitations": list(driver.limitations),
        "proposed_confidence": decision.final.proposed_confidence.value,
        "next_best_action_id": decision.final.next_best_action_id.value,
        "rationale": decision.final.rationale,
        "alternative_explanations": list(decision.final.alternative_explanations),
        "uncertainties": list(decision.final.uncertainties),
    }


class _FakeInteractions:
    """Test double that provides FakeInteractions behavior."""

    def __init__(self, response: object) -> None:
        """Initialize this test double with its controlled behavior."""

        self.response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> object:
        """Return the controlled provider response used by this test."""

        self.kwargs = kwargs
        return self.response


class _FakeClient:
    """Test double that provides FakeClient behavior."""

    def __init__(self, response: object) -> None:
        """Initialize this test double with its controlled behavior."""

        self.interactions = _FakeInteractions(response)


def _response(name: str, arguments: object) -> SimpleNamespace:
    """Create a controlled Gemini Interactions response."""

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
    """Verify that investigation state is frozen and budget bounded."""

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
    """Verify that finish proposal rejects duplicate evidence references."""

    with pytest.raises(ValidationError, match="unique"):
        FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary="A plausible driver.",
                    claim_type=ClaimType.ASSOCIATIONAL,
                    supporting_evidence_ids=("ev-1",),
                    no_material_counterevidence_reason=(
                        "No material counterevidence was identified."
                    ),
                    limitations=("The evidence is observational.",),
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
    """Verify that scripted backend exposes offered tools and exhaustion."""

    backend = ScriptedBackend([_tool_decision()])
    definitions = ToolRegistry().definitions((ToolName.CUSTOMER_TREND,))

    result = backend.decide_next_step(_state(), definitions)

    assert result.decision == _tool_decision()
    assert result.usage.decisions == 1
    assert backend.calls[0].allowed_tools == (ToolName.CUSTOMER_TREND,)
    with pytest.raises(ModelBackendError, match="exhausted"):
        backend.decide_next_step(_state(), definitions)


def test_scripted_backend_rejects_malformed_decision() -> None:
    """Verify that scripted backend rejects malformed decision."""

    backend = ScriptedBackend([{"kind": "tool", "selected_tool": "customer_trend"}])

    with pytest.raises(MalformedModelResponse, match="invalid"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_gemini_backend_sends_one_strict_function_decision() -> None:
    """Verify that gemini backend sends one strict function decision."""

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
    assert config.max_output_tokens == 4096
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


def test_gemini_function_schemas_ignore_model_docstrings_only() -> None:
    """Keep Python model docs out of Gemini schemas without losing field guidance."""

    definition = ToolDefinition(
        name=ToolName.CUSTOMER_TREND,
        description="Use the customer trend tool.",
        input_schema={
            "type": "object",
            "description": "This class documentation is for Python readers.",
            "properties": {
                "household_id": {
                    "type": "string",
                    "description": "The active household identifier.",
                }
            },
            "required": ["household_id"],
            "additionalProperties": False,
        },
    )

    response = _response(
        "customer_trend",
        {
            "investigation_question": "Did trip frequency fall?",
            "decision_summary": "Inspect frequency and value trajectory.",
            "arguments": {"household_id": "42"},
        },
    )
    client = _FakeClient(response)
    backend = GeminiFunctionCallingBackend(client=client)

    backend.decide_next_step(_state(), (definition,))

    functions = client.interactions.kwargs["tools"]
    analytical = next(item for item in functions if item.name == "customer_trend")
    finish = next(item for item in functions if item.name == "finish_investigation")
    parameters = analytical.parameters
    arguments = parameters["properties"]["arguments"]
    finish_parameters = finish.parameters

    assert "description" not in parameters
    assert "description" not in arguments
    assert (
        arguments["properties"]["household_id"]["description"]
        == "The active household identifier."
    )
    assert "description" not in finish_parameters
    assert "final" not in finish_parameters["properties"]
    assert set(finish_parameters["required"]) == set(finish_parameters["properties"])
    assert (
        finish_parameters["properties"]["driver_summary"]["description"]
        == "One qualitative primary driver without raw numerical claims."
    )


def test_gemini_backend_parses_finish_action() -> None:
    """Verify that gemini backend parses finish action."""

    client = _FakeClient(_response("finish_investigation", _finish_payload()))
    backend = GeminiFunctionCallingBackend(client=client)

    result = backend.decide_next_step(_state(), ())

    assert result.decision == _finish_decision()
    request = client.interactions.kwargs
    declarations = request["tools"]
    assert [item.name for item in declarations] == ["finish_investigation"]
    allowed_tools = request["generation_config"].tool_choice.allowed_tools
    assert request["generation_config"].max_output_tokens == 4096
    assert allowed_tools.mode == "any"
    assert allowed_tools.tools == ["finish_investigation"]
    assert "previous_interaction_id" not in request


@pytest.mark.parametrize(
    ("supporting", "counterevidence", "message"),
    (
        (["ev-trend", "ev-trend"], [], "duplicated"),
        (["ev-trend"], ["ev-counter", "ev-counter"], "duplicated"),
        (["ev-trend"], ["ev-trend"], "overlapped"),
        ([], ["ev-counter"], "requires a supported driver"),
    ),
)
def test_gemini_backend_rejects_inconsistent_flat_finish_evidence(
    supporting: list[str], counterevidence: list[str], message: str
) -> None:
    """Reject inconsistent model evidence roles instead of silently editing them."""

    payload = _finish_payload()
    payload["supporting_evidence_ids"] = supporting
    payload["counterevidence_ids"] = counterevidence
    backend = GeminiFunctionCallingBackend(
        client=_FakeClient(_response("finish_investigation", payload))
    )

    with pytest.raises(MalformedModelResponse, match=message):
        backend.decide_next_step(_state(), ())


def test_gemini_backend_preserves_counterevidence_and_supplies_safe_limitation() -> (
    None
):
    """Keep valid evidence roles and use a code-owned observational fallback."""

    payload = _finish_payload()
    payload["counterevidence_ids"] = ["ev-counter"]
    payload["limitations"] = ["", "   "]
    backend = GeminiFunctionCallingBackend(
        client=_FakeClient(_response("finish_investigation", payload))
    )

    result = backend.decide_next_step(_state(), ())

    assert isinstance(result.decision, FinishDecision)
    driver = result.decision.final.driver_summary[0]
    assert driver.counterevidence_ids == ("ev-counter",)
    assert driver.no_material_counterevidence_reason is None
    assert driver.limitations == (
        "The available evidence is observational and does not establish causation.",
    )


def test_gemini_backend_builds_driverless_insufficient_finish() -> None:
    """Keep an insufficient finish internally valid for deterministic verification."""

    payload = _finish_payload()
    payload["supporting_evidence_ids"] = []
    payload["next_best_action_id"] = "INSUFFICIENT_EVIDENCE"
    backend = GeminiFunctionCallingBackend(
        client=_FakeClient(_response("finish_investigation", payload))
    )

    result = backend.decide_next_step(_state(), ())

    assert isinstance(result.decision, FinishDecision)
    assert result.decision.final.driver_summary == ()
    assert result.decision.final.supporting_evidence_ids == ()
    assert result.decision.final.counterevidence_ids == ()


def test_gemini_backend_uses_function_call_id_for_stateless_response() -> None:
    """Verify that gemini backend uses function call id for stateless response."""

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
    """Verify that gemini backend rejects multiple function calls."""

    response = _response("customer_trend", {})
    response.steps.append(response.steps[0])
    backend = GeminiFunctionCallingBackend(client=_FakeClient(response))

    with pytest.raises(MalformedModelResponse, match="exactly one"):
        backend.decide_next_step(_state(), ToolRegistry().definitions())


def test_gemini_backend_rejects_unoffered_function() -> None:
    """Verify that gemini backend rejects unoffered function."""

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
    """Verify that gemini backend rejects incomplete response."""

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
    """Verify that gemini backend wraps malformed provider metadata."""

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
    """Verify that gemini backend rejects arguments outside the offered schema."""

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
    """Verify that gemini backend does not echo invalid provider payload."""

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


@pytest.mark.parametrize(
    ("status_code", "category"),
    (
        (400, "request rejected"),
        (401, "authentication rejected"),
        (403, "permission rejected"),
        (408, "request timed out"),
        (429, "quota or rate limit reached"),
        (500, "provider unavailable"),
        (502, "provider unavailable"),
        (503, "provider unavailable"),
        (504, "provider timed out"),
    ),
)
def test_gemini_backend_reports_safe_provider_status_without_leaking_content(
    status_code: int, category: str
) -> None:
    """Expose only application-authored status diagnostics for provider failures."""

    sensitive_marker = "AIza" + "a" * 35

    class _StatusError(RuntimeError):
        """Provider-style exception carrying both safe status and unsafe content."""

        def __init__(self) -> None:
            """Attach controlled status metadata and deliberately unsafe prose."""

            super().__init__(f"provider rejected {sensitive_marker}")
            self.status_code = status_code
            self.body = {"message": sensitive_marker}

    class _RaisingInteractions:
        """Raise the controlled provider exception for every request."""

        def create(self, **kwargs: Any) -> object:
            """Reject the request without inspecting its controlled arguments."""

            del kwargs
            raise _StatusError

    backend = GeminiFunctionCallingBackend(
        client=SimpleNamespace(interactions=_RaisingInteractions())
    )

    with pytest.raises(ModelBackendError) as caught:
        backend.decide_next_step(_state(), ())

    assert str(caught.value) == (
        f"Gemini Interactions request failed ({category}; HTTP {status_code})"
    )
    assert sensitive_marker not in str(caught.value)


def test_gemini_backend_accepts_legacy_numeric_provider_code_safely() -> None:
    """Classify the legacy SDK's numeric code without exposing its error body."""

    sensitive_marker = "synthetic-sensitive-legacy-provider-marker"

    class _LegacyStatusError(RuntimeError):
        """Legacy provider-style exception exposing a numeric code attribute."""

        code = 429

    error = _LegacyStatusError(sensitive_marker)

    class _RaisingInteractions:
        """Raise the controlled legacy provider exception for every request."""

        def create(self, **kwargs: Any) -> object:
            """Reject the request without inspecting its controlled arguments."""

            del kwargs
            raise error

    backend = GeminiFunctionCallingBackend(
        client=SimpleNamespace(interactions=_RaisingInteractions())
    )

    with pytest.raises(ModelBackendError) as caught:
        backend.decide_next_step(_state(), ())

    assert str(caught.value) == (
        "Gemini Interactions request failed (quota or rate limit reached; HTTP 429)"
    )
    assert sensitive_marker not in str(caught.value)


@pytest.mark.parametrize(
    ("provider_code", "expected_suffix"),
    (
        ("malformed_function_call", "; code malformed_function_call"),
        ("malformed_tool_call", "; code malformed_tool_call"),
        ("not-an-allowlisted-provider-value", ""),
    ),
)
def test_gemini_backend_allowlists_structured_interaction_error_codes(
    provider_code: str, expected_suffix: str
) -> None:
    """Retain only documented machine codes from the provider error envelope."""

    sensitive_marker = "synthetic-sensitive-error-message"

    class _StructuredStatusError(RuntimeError):
        """Provider-style HTTP error with a parsed Interactions envelope."""

        status_code = 400

        def __init__(self) -> None:
            """Attach one controlled Interactions error envelope for classification."""

            super().__init__(sensitive_marker)
            self.body = {
                "error": {
                    "code": provider_code,
                    "message": sensitive_marker,
                }
            }

    class _RaisingInteractions:
        """Raise the controlled structured provider exception."""

        def create(self, **kwargs: Any) -> object:
            """Reject the request without inspecting controlled arguments."""

            del kwargs
            raise _StructuredStatusError

    backend = GeminiFunctionCallingBackend(
        client=SimpleNamespace(interactions=_RaisingInteractions())
    )

    with pytest.raises(ModelBackendError) as caught:
        backend.decide_next_step(_state(), ())

    assert str(caught.value) == (
        "Gemini Interactions request failed "
        f"(request rejected; HTTP 400{expected_suffix})"
    )
    assert sensitive_marker not in str(caught.value)
    if expected_suffix:
        assert isinstance(caught.value, MalformedModelResponse)
    else:
        assert type(caught.value) is ModelBackendError
        assert provider_code not in str(caught.value)


def test_gemini_backend_keeps_unknown_provider_errors_generic() -> None:
    """Keep unknown provider errors generic and omit provider-authored content."""

    sensitive_marker = "synthetic-sensitive-provider-marker"

    class _RaisingInteractions:
        """Test double that provides RaisingInteractions behavior."""

        def create(self, **kwargs: Any) -> object:
            """Return the controlled provider response used by this test."""

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
    """Verify that gemini backend requires a key when no client is injected."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(MissingModelCredential, match="GEMINI_API_KEY"):
        GeminiFunctionCallingBackend()


def test_gemini_backend_passes_key_and_configures_one_interactions_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass the Gemini key explicitly and bound retryable Interactions failures."""

    captured: dict[str, Any] = {}

    def fake_client(**kwargs: Any) -> _FakeClient:
        """Return the fake Gemini client used by this test."""

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
    assert http_options.retry_options.attempts == 2
    assert http_options.retry_options.initial_delay == 5.0
    assert http_options.retry_options.max_delay == 5.0
    assert http_options.retry_options.exp_base == 2.0
    assert http_options.retry_options.jitter == 1.0
    assert http_options.retry_options.http_status_codes == [
        408,
        429,
        500,
        502,
        503,
        504,
    ]
