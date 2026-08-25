"""Direct OpenAI Responses API adapter for one strict decision per call."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from time import perf_counter
from typing import Any, Literal, Protocol, cast

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from whyback.agent.actions import ActionCatalog, load_action_catalog
from whyback.agent.backend import (
    BackendDecision,
    MalformedModelResponse,
    MissingModelCredential,
    ModelBackendError,
)
from whyback.agent.prompts import INVESTIGATOR_INSTRUCTIONS
from whyback.agent.state import (
    FinishDecision,
    FinishProposal,
    InvestigationState,
    ModelDecision,
    ModelUsage,
    ToolDecision,
)
from whyback.tools.contracts import ToolDefinition, ToolName

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]


class _ResponsesResource(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _ResponsesClient(Protocol):
    responses: _ResponsesResource


class _ToolPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    investigation_question: str = Field(min_length=1, max_length=300)
    decision_summary: str = Field(min_length=1, max_length=500)
    arguments: dict[str, JsonValue]


class _FinishPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    investigation_question: str = Field(min_length=1, max_length=300)
    decision_summary: str = Field(min_length=1, max_length=500)
    final: FinishProposal


def _strict_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Make every object field required as required by strict function schemas."""

    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, Mapping):
            properties = {
                str(name): _strict_schema(cast(Mapping[str, Any], child))
                if isinstance(child, Mapping)
                else child
                for name, child in value.items()
            }
            result[key] = properties
            result["required"] = list(properties)
        elif key in {"$defs", "definitions"} and isinstance(value, Mapping):
            result[key] = {
                str(name): _strict_schema(cast(Mapping[str, Any], child))
                if isinstance(child, Mapping)
                else child
                for name, child in value.items()
            }
        elif key == "items" and isinstance(value, Mapping):
            result[key] = _strict_schema(cast(Mapping[str, Any], value))
        elif key != "required":
            result[key] = value
    if result.get("type") == "object":
        result["additionalProperties"] = False
    return result


def _analytical_function(definition: ToolDefinition) -> dict[str, Any]:
    payload_schema = _ToolPayload.model_json_schema()
    arguments = cast(dict[str, Any], payload_schema["properties"])["arguments"]
    arguments.clear()
    arguments.update(definition.input_schema)
    return {
        "type": "function",
        "name": definition.name.value,
        "description": definition.description,
        "parameters": _strict_schema(payload_schema),
        "strict": True,
    }


def _finish_function() -> dict[str, Any]:
    return {
        "type": "function",
        "name": "finish_investigation",
        "description": (
            "Finish only when the available evidence supports a catalog action or an "
            "explicit insufficient-evidence result. Reference ledger evidence IDs and "
            "state limitations; use qualitative prose without raw numerical claims."
        ),
        "parameters": _strict_schema(_FinishPayload.model_json_schema()),
        "strict": True,
    }


class OpenAIResponsesBackend:
    """Issue stateless, bounded Responses API calls and parse one function call."""

    def __init__(
        self,
        *,
        model: str | None = None,
        reasoning_effort: ReasoningEffort = "medium",
        client: _ResponsesClient | None = None,
        timeout_seconds: float = 60.0,
        action_catalog: ActionCatalog | None = None,
    ) -> None:
        self._model_name = model or os.getenv("RETENTION_MODEL", "gpt-5.6-sol")
        self._reasoning_effort = reasoning_effort
        self._timeout_seconds = timeout_seconds
        self._action_catalog = action_catalog or load_action_catalog()
        if client is not None:
            self._client = client
        else:
            if not os.getenv("OPENAI_API_KEY"):
                raise MissingModelCredential(
                    "OPENAI_API_KEY is required for the openai backend"
                )
            self._client = cast(
                _ResponsesClient,
                OpenAI(timeout=timeout_seconds, max_retries=0),
            )

    @property
    def model_name(self) -> str:
        return self._model_name

    def decide_next_step(
        self,
        state: InvestigationState,
        tools: tuple[ToolDefinition, ...],
        *,
        repair_issues: tuple[str, ...] = (),
    ) -> BackendDecision:
        functions = [_analytical_function(tool) for tool in tools]
        functions.append(_finish_function())
        request_input = {
            "state": state.compact_model_context(),
            "action_catalog": self._action_catalog.compact_model_context(),
            "repair_issues": list(repair_issues),
        }
        safety_identifier = hashlib.sha256(
            f"whyback:{state.household_id}".encode()
        ).hexdigest()
        started = perf_counter()
        try:
            response = self._client.responses.create(
                model=self.model_name,
                instructions=INVESTIGATOR_INSTRUCTIONS,
                input=json.dumps(request_input, sort_keys=True, separators=(",", ":")),
                tools=functions,
                tool_choice="required",
                parallel_tool_calls=False,
                reasoning={"effort": self._reasoning_effort},
                max_output_tokens=1200,
                store=False,
                safety_identifier=safety_identifier,
                timeout=self._timeout_seconds,
            )
        except OpenAIError as error:
            raise ModelBackendError(
                f"OpenAI Responses request failed: {error}"
            ) from error
        latency_ms = (perf_counter() - started) * 1000
        response_status = getattr(response, "status", None)
        if response_status is not None and response_status != "completed":
            raise MalformedModelResponse(
                f"Response status was {response_status!r}, not 'completed'"
            )
        if getattr(response, "error", None) is not None:
            raise MalformedModelResponse("Response contained a provider error")
        raw_output = getattr(response, "output", None)
        if not isinstance(raw_output, (list, tuple)):
            raise MalformedModelResponse("Response output was not a sequence")
        output = cast(list[Any] | tuple[Any, ...], raw_output)
        calls = [
            item for item in output if getattr(item, "type", None) == "function_call"
        ]
        if len(calls) != 1:
            raise MalformedModelResponse(
                f"Expected exactly one function call; received {len(calls)}"
            )
        call = calls[0]
        call_status = getattr(call, "status", None)
        if call_status not in (None, "completed"):
            raise MalformedModelResponse(
                f"Function call status was {call_status!r}, not 'completed'"
            )
        try:
            arguments = json.loads(str(call.arguments))
            if not isinstance(arguments, dict):
                raise TypeError("Function arguments must be a JSON object")
            decision = self._parse_call(
                str(call.name),
                arguments,
                offered_tools={item.name: item for item in tools},
            )
        except (
            AttributeError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ) as error:
            raise MalformedModelResponse(
                f"Invalid function call payload: {error}"
            ) from error

        usage = getattr(response, "usage", None)
        try:
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            total_tokens = int(
                getattr(usage, "total_tokens", input_tokens + output_tokens)
                or input_tokens + output_tokens
            )
        except (TypeError, ValueError) as error:
            raise MalformedModelResponse(
                "Response usage contained a non-integer token count"
            ) from error
        raw_response_id = getattr(response, "id", None)
        if not isinstance(raw_response_id, str) or not raw_response_id.strip():
            raise MalformedModelResponse("Response did not include a provider ID")
        response_id = raw_response_id.strip()
        return BackendDecision(
            decision=decision,
            provider_call_id=response_id,
            model=self.model_name,
            usage=ModelUsage(
                decisions=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            ),
        )

    @staticmethod
    def _parse_call(
        name: str,
        raw: object,
        *,
        offered_tools: Mapping[ToolName, ToolDefinition],
    ) -> ModelDecision:
        if name == "finish_investigation":
            payload = _FinishPayload.model_validate(raw)
            return FinishDecision(
                investigation_question=payload.investigation_question,
                decision_summary=payload.decision_summary,
                final=payload.final,
            )
        try:
            tool_name = ToolName(name)
        except ValueError as error:
            raise ValueError(f"Unknown analytical function: {name}") from error
        definition = offered_tools.get(tool_name)
        if definition is None:
            raise ValueError(f"Analytical function was not offered: {name}")
        payload = _ToolPayload.model_validate(raw)
        properties = definition.input_schema.get("properties")
        required = definition.input_schema.get("required")
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            raise ValueError(f"Analytical function has an invalid schema: {name}")
        actual_keys = set(payload.arguments)
        allowed_keys = {str(key) for key in properties}
        required_keys = {str(key) for key in required}
        if not required_keys.issubset(actual_keys) or not actual_keys.issubset(
            allowed_keys
        ):
            raise ValueError(
                f"Analytical function arguments do not match the offered schema: {name}"
            )
        return ToolDecision(
            investigation_question=payload.investigation_question,
            decision_summary=payload.decision_summary,
            selected_tool=tool_name,
            arguments=payload.arguments,
        )
