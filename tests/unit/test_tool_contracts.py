from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from whyback.tools.contracts import (
    EvidenceRecord,
    PromotionResponseInput,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)

RUN_ID = UUID("00000000-0000-0000-0000-000000000001")


def _provenance() -> ToolProvenance:
    return ToolProvenance(normalized_parameters={"household_id": "1"})


def _evidence() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev_call_001",
        run_id=RUN_ID,
        household_id="1",
        source_tool=ToolName.PROMOTION_RESPONSE,
        source_tool_call_id="call",
        metric="promotion_share",
        value=0.5,
        unit="proportion",
    )


def test_tool_inputs_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PromotionResponseInput.model_validate(
            {"household_id": "1", "untrusted_override": True}
        )


def test_failed_result_cannot_carry_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot carry evidence"):
        ToolResult(
            tool_call_id="call",
            tool_name=ToolName.PROMOTION_RESPONSE,
            status=ToolStatus.RETRYABLE_ERROR,
            evidence=(_evidence(),),
            retryable=True,
            provenance=_provenance(),
        )


def test_partial_result_requires_limitation() -> None:
    with pytest.raises(ValidationError, match="must state a limitation"):
        ToolResult(
            tool_call_id="call",
            tool_name=ToolName.PROMOTION_RESPONSE,
            status=ToolStatus.PARTIAL,
            provenance=_provenance(),
        )


def test_only_retryable_error_can_be_retried() -> None:
    with pytest.raises(ValidationError, match="Only retryable_error"):
        ToolResult(
            tool_call_id="call",
            tool_name=ToolName.PROMOTION_RESPONSE,
            status=ToolStatus.FATAL_ERROR,
            retryable=True,
            provenance=_provenance(),
        )


def test_nonfinite_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        EvidenceRecord.model_validate(
            {
                **_evidence().model_dump(),
                "value": float("nan"),
            }
        )
