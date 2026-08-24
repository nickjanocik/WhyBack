"""Credential-free deterministic backend for orchestration tests and demos."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from whyback.agent.backend import (
    BackendDecision,
    MalformedModelResponse,
    ModelBackendError,
)
from whyback.agent.state import (
    MODEL_DECISION_ADAPTER,
    InvestigationState,
    ModelDecision,
    ModelUsage,
)
from whyback.tools.contracts import ToolDefinition, ToolName


@dataclass(frozen=True, slots=True)
class ScriptedCall:
    """Observable input boundary captured without hidden reasoning."""

    decision_number: int
    allowed_tools: tuple[ToolName, ...]
    remaining_tool_budget: int
    remaining_turn_budget: int
    repair_issues: tuple[str, ...]


class ScriptedBackend:
    """Yield predeclared decisions while exercising the real application loop."""

    def __init__(
        self,
        decisions: Sequence[ModelDecision | Mapping[str, Any]],
        *,
        model_name: str = "scripted/whyback-v1",
    ) -> None:
        self._decisions = tuple(decisions)
        self._model_name = model_name
        self._position = 0
        self.calls: list[ScriptedCall] = []

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
        if self._position >= len(self._decisions):
            raise ModelBackendError("ScriptedBackend exhausted its decision script")
        self.calls.append(
            ScriptedCall(
                decision_number=state.model_usage.decisions + 1,
                allowed_tools=tuple(item.name for item in tools),
                remaining_tool_budget=state.remaining_tool_budget,
                remaining_turn_budget=state.remaining_turn_budget,
                repair_issues=repair_issues,
            )
        )
        raw = self._decisions[self._position]
        self._position += 1
        try:
            decision = MODEL_DECISION_ADAPTER.validate_python(raw)
        except ValidationError as error:
            raise MalformedModelResponse(
                f"Scripted decision {self._position} is invalid: {error}"
            ) from error
        return BackendDecision(
            decision=decision,
            provider_call_id=f"scripted-{self._position:03d}",
            model=self.model_name,
            usage=ModelUsage(decisions=1),
        )
