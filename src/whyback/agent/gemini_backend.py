"""Gemini Interactions adapter for one strict function decision per request."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any, Literal, Protocol, cast

from google import genai
from google.genai import interactions, types
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


class _InteractionsResource(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _GeminiClient(Protocol):
    interactions: _InteractionsResource


class _FunctionCall(Protocol):
    id: object
    name: object
    arguments: object


ThinkingLevel = Literal["low", "medium", "high"]


class _ToolPayload(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    investigation_question: str = Field(min_length=1, max_length=300)
    decision_summary: str = Field(min_length=1, max_length=500)
    arguments: dict[str, JsonValue]


class _FinishPayload(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    investigation_question: str = Field(min_length=1, max_length=300)
    decision_summary: str = Field(min_length=1, max_length=500)
    final: FinishProposal


class _CallContractError(ValueError):
    """A safe, application-authored explanation of a rejected function call."""


def _inline_local_references(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Inline Pydantic's local definitions for the Interactions JSON schema."""

    raw_definitions = schema.get("$defs", schema.get("definitions", {}))
    definitions = raw_definitions if isinstance(raw_definitions, Mapping) else {}

    def expand(value: object, active: frozenset[str]) -> object:
        if isinstance(value, Mapping):
            raw_ref = value.get("$ref")
            ref_prefix = next(
                (
                    prefix
                    for prefix in ("#/$defs/", "#/definitions/")
                    if isinstance(raw_ref, str) and raw_ref.startswith(prefix)
                ),
                None,
            )
            if isinstance(raw_ref, str) and ref_prefix is not None:
                name = raw_ref.removeprefix(ref_prefix)
                target = definitions.get(name)
                if not isinstance(target, Mapping) or name in active:
                    raise ValueError(
                        "Function schema contained an invalid local reference"
                    )
                expanded = expand(target, active | {name})
                if not isinstance(expanded, dict):
                    raise ValueError(
                        "Function schema reference did not resolve to an object"
                    )
                siblings = {
                    str(key): expand(child, active)
                    for key, child in value.items()
                    if key != "$ref"
                }
                return {**expanded, **siblings}
            return {
                str(key): expand(child, active)
                for key, child in value.items()
                if key not in {"$defs", "definitions"}
            }
        if isinstance(value, list):
            return [expand(item, active) for item in value]
        return value

    expanded_schema = expand(schema, frozenset())
    if not isinstance(expanded_schema, dict):
        raise ValueError("Function schema did not resolve to an object")
    return expanded_schema


def _closed_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively close objects and require every declared model field."""

    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "required":
            continue
        if isinstance(value, Mapping):
            result[key] = _closed_schema(cast(Mapping[str, Any], value))
        elif isinstance(value, list):
            result[key] = [
                _closed_schema(cast(Mapping[str, Any], item))
                if isinstance(item, Mapping)
                else item
                for item in value
            ]
        else:
            result[key] = value
    properties = result.get("properties")
    if isinstance(properties, Mapping):
        result["required"] = list(properties)
    if result.get("type") == "object":
        result["additionalProperties"] = False
    return result


def _interaction_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a closed, reference-free JSON schema for Interactions tools."""

    return _closed_schema(_inline_local_references(schema))


def _analytical_function(definition: ToolDefinition) -> interactions.Function:
    payload_schema = _ToolPayload.model_json_schema()
    arguments = cast(dict[str, Any], payload_schema["properties"])["arguments"]
    if not isinstance(arguments, dict):
        raise ValueError("Tool payload schema did not contain an arguments object")
    arguments.clear()
    arguments.update(definition.input_schema)
    return interactions.Function(
        name=definition.name.value,
        description=definition.description,
        parameters=_interaction_schema(payload_schema),
    )


def _finish_function() -> interactions.Function:
    return interactions.Function(
        name="finish_investigation",
        description=(
            "Finish only when the available evidence supports a catalog action or an "
            "explicit insufficient-evidence result. Reference ledger evidence IDs and "
            "state limitations; use qualitative prose without raw numerical claims."
        ),
        parameters=_interaction_schema(_FinishPayload.model_json_schema()),
    )


def _nonnegative_token_count(usage: object, field: str) -> int:
    raw = getattr(usage, field, None) if usage is not None else None
    if raw is None:
        return 0
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise MalformedModelResponse("Response usage contained an invalid token count")
    return raw


class GeminiFunctionCallingBackend:
    """Issue stateless, bounded Gemini Interactions calls and parse one function."""

    def __init__(
        self,
        *,
        model: str | None = None,
        thinking_level: ThinkingLevel = "medium",
        client: _GeminiClient | None = None,
        timeout_seconds: float = 60.0,
        action_catalog: ActionCatalog | None = None,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive finite number")
        self._model_name = model or os.getenv("RETENTION_MODEL", "gemini-3.7-flash")
        self._thinking_level = thinking_level
        self._timeout_milliseconds = max(1, round(timeout_seconds * 1000))
        self._action_catalog = action_catalog or load_action_catalog()
        self._http_options = types.HttpOptions(
            api_version="v1",
            timeout=self._timeout_milliseconds,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        if client is not None:
            self._client = client
        else:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key is None or not api_key.strip():
                raise MissingModelCredential(
                    "GEMINI_API_KEY is required for the gemini backend"
                )
            # Pass the key explicitly so GOOGLE_API_KEY cannot take precedence.
            self._client = cast(
                _GeminiClient,
                genai.Client(api_key=api_key.strip(), http_options=self._http_options),
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
        declarations = [_analytical_function(tool) for tool in tools]
        declarations.append(_finish_function())
        allowed_names = [
            declaration.name
            for declaration in declarations
            if isinstance(declaration.name, str)
        ]
        request_input = {
            "state": state.compact_model_context(),
            "action_catalog": self._action_catalog.compact_model_context(),
            "repair_issues": list(repair_issues),
        }
        generation_config = interactions.GenerationConfig(
            max_output_tokens=1200,
            thinking_level=cast(Literal["low", "medium", "high"], self._thinking_level),
            thinking_summaries="none",
            tool_choice=interactions.ToolChoiceConfig(
                allowed_tools=interactions.AllowedTools(
                    mode="any",
                    tools=allowed_names,
                )
            ),
        )
        started = perf_counter()
        try:
            response = self._client.interactions.create(
                model=self.model_name,
                input=json.dumps(
                    request_input,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                system_instruction=INVESTIGATOR_INSTRUCTIONS,
                tools=declarations,
                generation_config=generation_config,
                store=False,
                stream=False,
                api_version="v1",
                timeout=self._timeout_milliseconds / 1000,
            )
        except Exception:
            # Provider exception bodies can contain request details or credentials.
            raise ModelBackendError("Gemini Interactions request failed") from None
        latency_ms = (perf_counter() - started) * 1000

        call = self._extract_one_call(response)
        try:
            raw_name = call.name
            raw_arguments = call.arguments
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise _CallContractError("Function call did not include a name")
            if not isinstance(raw_arguments, Mapping):
                raise _CallContractError("Function arguments were not a JSON object")
            decision = self._parse_call(
                raw_name,
                dict(raw_arguments),
                offered_tools={item.name: item for item in tools},
            )
        except _CallContractError as error:
            raise MalformedModelResponse(str(error)) from error
        except (AttributeError, TypeError, ValueError, ValidationError):
            # Do not echo provider-authored values or Pydantic input excerpts.
            raise MalformedModelResponse("Invalid function call payload") from None

        usage = getattr(response, "usage", None)
        input_tokens = _nonnegative_token_count(usage, "total_input_tokens")
        output_tokens = _nonnegative_token_count(usage, "total_output_tokens")
        raw_total_tokens = _nonnegative_token_count(usage, "total_tokens")
        total_tokens = raw_total_tokens or input_tokens + output_tokens
        if total_tokens < input_tokens + output_tokens:
            raise MalformedModelResponse(
                "Response usage token counts did not reconcile"
            )

        raw_response_id = getattr(response, "id", None)
        raw_call_id = getattr(call, "id", None)
        provider_id = next(
            (
                value.strip()
                for value in (raw_response_id, raw_call_id)
                if isinstance(value, str) and value.strip()
            ),
            None,
        )
        if provider_id is None:
            raise MalformedModelResponse(
                "Response did not include an interaction or function-call ID"
            )
        return BackendDecision(
            decision=decision,
            provider_call_id=provider_id,
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
    def _extract_one_call(response: object) -> _FunctionCall:
        if getattr(response, "errors", None):
            raise MalformedModelResponse("Interaction contained provider errors")
        if getattr(response, "status", None) != "requires_action":
            raise MalformedModelResponse(
                "Function-call interaction did not require action"
            )
        raw_steps = getattr(response, "steps", None)
        if not isinstance(raw_steps, Sequence) or isinstance(
            raw_steps, (str, bytes, bytearray)
        ):
            raise MalformedModelResponse("Response steps were not a sequence")
        calls = [
            step for step in raw_steps if getattr(step, "type", None) == "function_call"
        ]
        if len(calls) != 1:
            raise MalformedModelResponse(
                f"Expected exactly one function call; received {len(calls)}"
            )
        return cast(_FunctionCall, calls[0])

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
            raise _CallContractError(
                "Model selected an unknown analytical function"
            ) from error
        definition = offered_tools.get(tool_name)
        if definition is None:
            raise _CallContractError("Model selected a function that was not offered")
        payload = _ToolPayload.model_validate(raw)
        properties = definition.input_schema.get("properties")
        required = definition.input_schema.get("required")
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            raise _CallContractError(
                "Offered analytical function had an invalid schema"
            )
        actual_keys = set(payload.arguments)
        allowed_keys = {str(key) for key in properties}
        required_keys = {str(key) for key in required}
        if not required_keys.issubset(actual_keys) or not actual_keys.issubset(
            allowed_keys
        ):
            raise _CallContractError(
                "Function arguments did not match the offered schema"
            )
        return ToolDecision(
            investigation_question=payload.investigation_question,
            decision_summary=payload.decision_summary,
            selected_tool=tool_name,
            arguments=payload.arguments,
        )
