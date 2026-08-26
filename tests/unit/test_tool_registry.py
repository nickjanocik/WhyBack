"""Tests for WhyBack's tool registry behavior."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.tools.contracts import (
    AnalysisWindow,
    ToolExecutionContext,
    ToolName,
    ToolStatus,
)
from whyback.tools.registry import ToolRegistry


def _context() -> ToolExecutionContext:
    """Create the context value used by these tests."""

    return ToolExecutionContext(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        tool_call_id="call",
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=1,
            recent_start=2,
            recent_end=2,
        ),
    )


def test_registry_exposes_exactly_six_strict_tool_definitions() -> None:
    """Verify that registry exposes exactly six strict tool definitions."""

    registry = ToolRegistry()

    definitions = registry.definitions()

    assert {definition.name for definition in definitions} == set(ToolName)
    assert len(definitions) == 6
    assert all(
        definition.input_schema["additionalProperties"] is False
        for definition in definitions
    )
    assert all("Requires" in definition.description for definition in definitions)


def test_normalized_arguments_include_defaults_and_ignore_key_order() -> None:
    """Verify that normalized arguments include defaults and ignore key order."""

    registry = ToolRegistry()

    first, first_key = registry.normalize_arguments(
        ToolName.CATEGORY_DECOMPOSITION,
        {"household_id": "1"},
    )
    second, second_key = registry.normalize_arguments(
        ToolName.CATEGORY_DECOMPOSITION,
        {"top_n": 8, "household_id": "1"},
    )

    assert first.model_dump() == second.model_dump()
    assert first_key == second_key


def test_invalid_arguments_return_typed_failure_without_evidence(
    tmp_path: Path,
) -> None:
    """Verify that invalid arguments return typed failure without evidence."""

    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    registry = ToolRegistry()
    with DataRepository(tmp_path) as repository:
        result = registry.execute(
            ToolName.CATEGORY_DECOMPOSITION,
            {"household_id": "1", "unknown": True},
            _context(),
            repository,
        )

    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.evidence == ()
    assert not result.retryable
