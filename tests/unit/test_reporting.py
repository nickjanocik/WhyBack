from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from whyback.agent.actions import ActionId
from whyback.agent.runner import InvestigationOutcome
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishProposal,
    InvestigationState,
    ResolvedConfidence,
    RunStatus,
    ToolAttemptRecord,
    ToolHistoryEntry,
)
from whyback.agent.verifier import VerificationResult, VerifiedFinalDecision
from whyback.detection.decline import DeclineSnapshot
from whyback.observability import AuditEvent, AuditEventName, AuditJsonlWriter
from whyback.reporting import (
    build_report_data,
    build_trace_view,
    render_report_html,
    render_report_json,
    render_report_markdown,
    render_trace_html,
    write_report_bundle,
    write_trace_html,
)
from whyback.tools.contracts import EvidenceRecord, ToolName, ToolStatus

RUN_ID = UUID("00000000-0000-0000-0000-000000000181")
CALL_ID = "call-report-category"
SUPPORT_ID = "ev-support-category"
COUNTER_ID = "ev-counter-category"


def _snapshot() -> DeclineSnapshot:
    return DeclineSnapshot(
        household_id="181",
        baseline_start_week=38,
        baseline_end_week=45,
        recent_start_week=46,
        recent_end_week=53,
        baseline_retailer_sales_value=120.0,
        recent_retailer_sales_value=60.0,
        baseline_distinct_baskets=8,
        recent_distinct_baskets=4,
        baseline_active_weeks=8,
        recent_active_weeks=4,
        sales_drop=0.5,
        trip_drop=0.5,
        active_week_drop=0.5,
        decline_score=0.5,
        eligible=True,
        flagged=True,
        partial_week_limitation="The final week may be partial.",
    )


def _evidence(
    evidence_id: str,
    *,
    category: str,
    baseline: float,
    recent: float,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id="181",
        source_tool=ToolName.CATEGORY_DECOMPOSITION,
        source_tool_call_id=CALL_ID,
        metric="category_retailer_sales_value",
        dimensions={"category": category},
        baseline_value=baseline,
        recent_value=recent,
        change=recent - baseline,
        unit="retailer_sales_value",
        limitations=("UNKNOWN mappings remain visible.",),
        query_hash="query-hash",
    )


def _outcome() -> InvestigationOutcome:
    support = _evidence(
        SUPPORT_ID,
        category="<script>alert('x')</script>",
        baseline=90.0,
        recent=30.0,
    )
    counter = _evidence(
        COUNTER_ID,
        category="Growing category",
        baseline=10.0,
        recent=20.0,
    )
    history = ToolHistoryEntry(
        decision_number=1,
        tool_name=ToolName.CATEGORY_DECOMPOSITION,
        normalized_signature="signature",
        investigation_question="Which category changed?",
        decision_summary="Inspect the category composition.",
        normalized_arguments={"household_id": "181", "top_n": 8},
        attempts=(
            ToolAttemptRecord(
                attempt=1,
                tool_call_id=CALL_ID,
                status=ToolStatus.PARTIAL,
                elapsed_ms=12.5,
                limitations=("The result retained UNKNOWN mappings.",),
            ),
        ),
        final_status=ToolStatus.PARTIAL,
        evidence_ids=(SUPPORT_ID, COUNTER_ID),
        limitations=("The result retained UNKNOWN mappings.",),
    )
    driver = DriverClaim(
        summary="<script>alert('x')</script> is a plausible category driver.",
        supporting_evidence_ids=(SUPPORT_ID,),
    )
    proposal = FinishProposal(
        driver_summary=(driver,),
        proposed_confidence=ConfidenceLevel.HIGH,
        supporting_evidence_ids=(SUPPORT_ID,),
        counterevidence_ids=(COUNTER_ID,),
        next_best_action_id=ActionId.CATEGORY_WINBACK.value,
        rationale="A raw model claim says 999%, which must not be rendered.",
        alternative_explanations=(
            "<img src=x onerror=alert('x')> behavior may be outside the retailer.",
        ),
        uncertainties=("Customer intent is not recorded.",),
    )
    verified = VerifiedFinalDecision(
        drivers=(driver,),
        proposed_confidence=ConfidenceLevel.HIGH,
        resolved_confidence=ResolvedConfidence.MEDIUM,
        confidence_cap_applied=True,
        supporting_evidence_ids=(SUPPORT_ID,),
        counterevidence_ids=(COUNTER_ID,),
        next_best_action_id=ActionId.CATEGORY_WINBACK,
        action_description="Recommend a human-reviewed category test.",
        rationale=proposal.rationale,
        alternative_explanations=proposal.alternative_explanations,
        uncertainties=proposal.uncertainties,
        propagated_limitations=("The result retained UNKNOWN mappings.",),
        human_review_required=True,
        recommended_success_metric=(
            "Change in retailer sales value relative to an eligible holdout."
        ),
        suggested_experiment="Use a reviewer-approved randomized holdout.",
    )
    state = InvestigationState.start(_snapshot(), run_id=RUN_ID).model_copy(
        update={
            "tool_history": (history,),
            "evidence_ledger": (support, counter),
            "failed_or_partial_tools": (ToolName.CATEGORY_DECOMPOSITION,),
            "remaining_tool_budget": 4,
            "remaining_turn_budget": 4,
            "run_status": RunStatus.COMPLETED,
            "final_proposal": proposal,
            "resolved_confidence": ResolvedConfidence.MEDIUM,
        }
    )
    return InvestigationOutcome(
        state=state,
        verification=VerificationResult(passed=True, final=verified),
    )


def test_report_boundary_resolves_evidence_and_preserves_status_limitations() -> None:
    report = build_report_data(_outcome())

    assert report.decline.baseline_retailer_sales_value == 120.0
    assert report.decline.recent_retailer_sales_value == 60.0
    assert [item.evidence_id for item in report.supporting_evidence] == [SUPPORT_ID]
    assert [item.evidence_id for item in report.counterevidence] == [COUNTER_ID]
    assert report.supporting_evidence[0].baseline_value == 90.0
    assert report.supporting_evidence[0].recent_value == 30.0
    assert report.supporting_evidence[0].source_status is ToolStatus.PARTIAL
    assert report.supporting_evidence[0].role == "supporting"
    assert report.counterevidence[0].role == "counterevidence"
    assert report.tool_warnings[0].final_status is ToolStatus.PARTIAL
    assert "The result retained UNKNOWN mappings." in report.limitations
    assert report.action is not None and report.action.human_review_required
    with pytest.raises(TypeError, match="immutable"):
        report.supporting_evidence[0].dimensions["category"] = "mutated"


def test_json_and_markdown_have_required_sections_and_no_model_numbers() -> None:
    report = build_report_data(_outcome())

    json_text = render_report_json(report)
    markdown = render_report_markdown(report)
    parsed = json.loads(json_text)

    assert parsed["supporting_evidence"][0]["baseline_value"] == 90.0
    assert parsed["decline"]["decline_score"] == 0.5
    assert "999" not in json_text
    assert "999" not in markdown
    assert markdown.endswith("\n")
    assert not markdown.endswith("\n\n")
    for section in (
        "Decline summary",
        "Investigation path",
        "Likely drivers",
        "Supporting evidence",
        "Counterevidence and alternative explanations",
        "Next Best Action",
        "Measurement plan",
        "Limitations",
        "Failures and partial-result warnings",
        "Human-review requirement",
    ):
        assert f"## {section}" in markdown
    assert SUPPORT_ID in markdown
    assert "Partial" in markdown
    assert "UNKNOWN mappings remain visible" in markdown
    assert "&lt;script&gt;" in markdown
    assert f"`{SUPPORT_ID}`" in markdown
    assert "`ev\\_support\\_category`" not in markdown
    assert "\n- Baseline: 90" in markdown
    assert "\n- Recent: 30" in markdown
    assert "\n- Change: -60" in markdown
    assert "\n## Counterevidence and alternative explanations\n" in markdown
    assert "\n- Alternative:" in markdown


def test_markdown_keeps_ordered_investigation_steps_on_separate_lines() -> None:
    outcome = _outcome()
    first = outcome.state.tool_history[0]
    second = first.model_copy(
        update={
            "decision_number": 2,
            "tool_name": ToolName.BASKET_BEHAVIOR,
            "normalized_signature": "basket-signature",
            "investigation_question": "Did basket cadence change?",
        }
    )
    state = outcome.state.model_copy(update={"tool_history": (first, second)})

    markdown = render_report_markdown(
        build_report_data(outcome.model_copy(update={"state": state}))
    )

    assert "\n1. **Category decomposition**" in markdown
    assert "\n2. **Basket behavior**" in markdown
    assert "`ev-counter-category`\n\n2. **Basket behavior**" in markdown


def test_report_schema_rejects_lifecycle_and_evidence_owner_conflicts() -> None:
    report = build_report_data(_outcome())
    missing_action = report.model_dump(mode="json")
    missing_action["action"] = None
    with pytest.raises(ValidationError, match="completed report"):
        type(report).model_validate(missing_action)

    wrong_owner = report.model_dump(mode="json")
    wrong_owner["evidence_ledger"][0]["household_id"] = "different"
    with pytest.raises(ValidationError, match="belong"):
        type(report).model_validate(wrong_owner)


def test_html_is_escaped_self_contained_and_auditable() -> None:
    html = render_report_html(build_report_data(_outcome()))

    assert html.startswith("<!doctype html>")
    assert "WhyBack" in html
    assert "Find the why. Choose the way back." in html
    assert SUPPORT_ID in html
    assert "Source status" in html or "Partial" in html
    assert "UNKNOWN mappings remain visible." in html
    assert "&lt;script&gt;alert" in html
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "999" not in html
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html and "<link" not in html
    for section_id in (
        "decline-summary",
        "investigation-path",
        "likely-drivers",
        "supporting-evidence",
        "counterevidence-alternatives",
        "next-best-action",
        "measurement-plan",
        "limitations",
        "failures-partial-warnings",
        "human-review",
    ):
        assert f'id="{section_id}"' in html


def _trace_event(
    name: AuditEventName,
    offset: int,
    details: dict[str, object],
) -> AuditEvent:
    return AuditEvent(
        timestamp=datetime(2026, 8, 24, 12, tzinfo=UTC) + timedelta(seconds=offset),
        event=name,
        run_id=RUN_ID,
        household_id="181",
        details=details,
    )


def test_trace_viewer_reads_jsonl_and_exposes_chronology_and_controls(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "run.trace.jsonl"
    events = (
        _trace_event(AuditEventName.RUN_STARTED, 0, {"status": "running"}),
        _trace_event(
            AuditEventName.MODEL_DECISION_RECEIVED,
            1,
            {"decision_kind": "tool", "summary": "<script>bad()</script>"},
        ),
        _trace_event(
            AuditEventName.TOOL_STARTED,
            2,
            {"tool_name": "category_decomposition", "attempt": 1},
        ),
        _trace_event(
            AuditEventName.TOOL_FAILED,
            3,
            {
                "tool_name": "category_decomposition",
                "status": "retryable_error",
                "elapsed_ms": 12.5,
            },
        ),
        _trace_event(
            AuditEventName.RETRY_SCHEDULED,
            4,
            {"tool_name": "category_decomposition", "next_attempt": 2},
        ),
        _trace_event(
            AuditEventName.TOOL_STARTED,
            5,
            {"tool_name": "category_decomposition", "attempt": 2},
        ),
        _trace_event(
            AuditEventName.TOOL_PARTIAL,
            6,
            {
                "tool_name": "category_decomposition",
                "status": "partial",
                "latency_ms": 7.5,
                "evidence_ids": [SUPPORT_ID],
            },
        ),
        _trace_event(
            AuditEventName.VERIFICATION_PASSED,
            7,
            {"next_best_action_id": "CATEGORY_WINBACK", "status": "passed"},
        ),
        _trace_event(
            AuditEventName.RUN_COMPLETED,
            8,
            {"run_status": "completed", "final_action": "CATEGORY_WINBACK"},
        ),
    )
    with AuditJsonlWriter(trace_path) as writer:
        for event in events:
            writer.append(event)

    trace_view = build_trace_view(events)
    with pytest.raises(TypeError, match="immutable"):
        trace_view.events[0].details["new"] = "mutated"
    html = render_trace_html(trace_path)

    assert html.index("Investigation started") < html.index("Decision received")
    assert html.index("Bounded retry scheduled") < html.index(
        "Tool returned partial evidence"
    )
    assert "category_decomposition" in html
    assert "retry attempt 2" in html
    assert "12.5 ms" in html and "7.5 ms" in html
    assert SUPPORT_ID in html
    assert "verifier passed" in html
    assert "final action CATEGORY_WINBACK" in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "<script>bad" not in html
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html and "<link" not in html


def test_bundle_and_trace_outputs_open_without_sibling_assets(tmp_path: Path) -> None:
    bundle = write_report_bundle(_outcome(), tmp_path / "report", stem="household")
    assert bundle.json.name == "household.json"
    assert bundle.markdown.name == "household.md"
    assert bundle.html.name == "household.html"
    assert all(path.is_file() for path in (bundle.json, bundle.markdown, bundle.html))
    assert "<base" not in bundle.html.read_text(encoding="utf-8")

    trace_path = tmp_path / "trace.jsonl"
    with AuditJsonlWriter(trace_path) as writer:
        writer.append(_trace_event(AuditEventName.RUN_STARTED, 0, {}))
    viewer = write_trace_html(trace_path, tmp_path / "viewer" / "index.html")
    viewer_html = viewer.read_text(encoding="utf-8")
    assert viewer.is_file()
    assert "<base" not in viewer_html
    assert "Static, self-contained viewer" in viewer_html
