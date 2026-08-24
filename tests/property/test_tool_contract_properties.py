from __future__ import annotations

from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from whyback.tools.common import EvidenceFactory
from whyback.tools.contracts import AnalysisWindow, ToolExecutionContext, ToolName


@given(count=st.integers(min_value=1, max_value=200))
def test_evidence_ids_are_unique_within_a_tool_call(count: int) -> None:
    context = ToolExecutionContext(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        tool_call_id="property-call",
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=8,
            recent_start=9,
            recent_end=16,
        ),
    )
    factory = EvidenceFactory(context, ToolName.CUSTOMER_TREND)

    identifiers = [
        factory.add("metric", value=float(index)).evidence_id for index in range(count)
    ]

    assert len(identifiers) == len(set(identifiers))
