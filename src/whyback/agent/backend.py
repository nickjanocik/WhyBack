"""Provider-neutral boundary for fresh model decisions."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from whyback.agent.state import InvestigationState, ModelDecision, ModelUsage
from whyback.tools.contracts import ToolDefinition


class ModelBackendError(RuntimeError):
    """A model request failed before yielding a valid decision."""


class MissingModelCredential(ModelBackendError):
    """The live backend was selected without an API credential."""


class MalformedModelResponse(ModelBackendError):
    """The provider response did not contain exactly one valid action."""


class BackendDecision(BaseModel):
    """One parsed decision plus provider metadata safe for audit logs."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decision: ModelDecision
    provider_call_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    usage: ModelUsage


class ModelBackend(Protocol):
    """Describe the interface every live or scripted model backend must provide."""

    @property
    def model_name(self) -> str:
        """Return the stable model name recorded in run provenance."""

        ...

    def decide_next_step(
        self,
        state: InvestigationState,
        tools: tuple[ToolDefinition, ...],
        *,
        repair_issues: tuple[str, ...] = (),
    ) -> BackendDecision:
        """Choose one offered tool or propose a final answer from compact state."""

        ...
