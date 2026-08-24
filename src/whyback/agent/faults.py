"""Explicit demo-only fault injection for deterministic reliability exercises."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import JsonValue

from whyback.tools.contracts import (
    ToolExecutionContext,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)


class DemoFaultConfigurationError(ValueError):
    """A demo fault was unknown or not explicitly acknowledged."""


class DemoFaultScenario(StrEnum):
    """The complete allowlist of non-production injected failures."""

    PROMOTION_TIMEOUT_ONCE = "promotion_response:timeout-once"
    PROMOTION_TIMEOUT_ALWAYS = "promotion_response:timeout-always"


class DemoFaultInjector:
    """Return typed synthetic failures only after explicit demo acknowledgement."""

    def __init__(
        self,
        scenario: DemoFaultScenario,
        *,
        enabled: Literal[True],
    ) -> None:
        if enabled is not True:
            raise DemoFaultConfigurationError(
                "Demo fault injection requires enabled=True acknowledgement"
            )
        self.scenario = scenario

    @classmethod
    def from_spec(
        cls,
        spec: str,
        *,
        enabled: Literal[True],
    ) -> DemoFaultInjector:
        try:
            scenario = DemoFaultScenario(spec)
        except ValueError as error:
            raise DemoFaultConfigurationError(
                f"Unknown demo fault scenario: {spec}"
            ) from error
        return cls(scenario, enabled=enabled)

    def intercept(
        self,
        *,
        name: ToolName,
        attempt: int,
        context: ToolExecutionContext,
        normalized_parameters: dict[str, JsonValue],
    ) -> ToolResult | None:
        """Return a retryable timeout when the allowlisted scenario applies."""

        if name is not ToolName.PROMOTION_RESPONSE:
            return None
        should_fail = self.scenario is DemoFaultScenario.PROMOTION_TIMEOUT_ALWAYS or (
            self.scenario is DemoFaultScenario.PROMOTION_TIMEOUT_ONCE and attempt == 1
        )
        if not should_fail:
            return None
        limitation = (
            "Demo-only injected promotion_response timeout; no analytical query "
            "was executed for this attempt."
        )
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=name,
            status=ToolStatus.RETRYABLE_ERROR,
            limitations=(limitation,),
            retryable=True,
            provenance=ToolProvenance(
                dataset_source_commit=context.source_commit,
                source_hashes=context.source_hashes,
                normalized_parameters=normalized_parameters,
                rows_examined=0,
                application_version=context.application_version,
                diagnostics={
                    "demo_fault": True,
                    "scenario": self.scenario.value,
                    "attempt": attempt,
                },
            ),
        )
