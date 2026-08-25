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
from whyback.agent.verifier import (
    ConfidenceAdjustment,
    VerificationResult,
    VerifiedFinalDecision,
)
from whyback.detection.decline import DeclineSnapshot
from whyback.methodology import ClaimType, ContextClassification
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
PEER_CALL_ID = "call-report-peer"


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
        claim_type=ClaimType.ASSOCIATIONAL,
        supporting_evidence_ids=(SUPPORT_ID,),
        counterevidence_ids=(COUNTER_ID,),
        limitations=("This is an observational association.",),
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
        confidence_adjustments=(
            ConfidenceAdjustment(
                context_classification=ContextClassification.INSUFFICIENT_CONTEXT,
                maximum_confidence=ResolvedConfidence.MEDIUM,
                reason=(
                    "Population or peer context is insufficient, so missing "
                    "comparison evidence cannot be treated as neutral."
                ),
            ),
            ConfidenceAdjustment(
                context_classification=ContextClassification.INSUFFICIENT_CONTEXT,
                maximum_confidence=ResolvedConfidence.MEDIUM,
                reason=(
                    "The category comparison cohort is insufficient, so the cited "
                    "loss cannot receive high customer-specific confidence."
                ),
            ),
        ),
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


def _outcome_with_population_context() -> InvestigationOutcome:
    outcome = _outcome()
    values = {
        "target_retailer_sales_change": -0.50,
        "population_household_count": 20.0,
        "population_median_retailer_sales_change": -0.10,
        "population_retailer_sales_change_q25": -0.20,
        "population_retailer_sales_change_q75": 0.0,
        "target_population_retailer_sales_change_percentile": 5.0,
        "population_declining_household_share": 0.40,
        "target_minus_population_median_change": -0.40,
        "peer_household_count": 5.0,
        "peer_median_retailer_sales_change": -0.05,
        "peer_retailer_sales_change_q25": -0.10,
        "peer_retailer_sales_change_q75": 0.02,
        "target_peer_retailer_sales_change_percentile": 0.0,
        "peer_declining_household_share": 0.20,
        "target_minus_peer_median_change": -0.45,
    }
    records = tuple(
        EvidenceRecord(
            evidence_id=f"ev-peer-{index:02d}",
            run_id=RUN_ID,
            household_id="181",
            source_tool=ToolName.PEER_COMPARISON,
            source_tool_call_id=PEER_CALL_ID,
            metric=metric,
            dimensions={
                "target_excluded": "true",
                "cohort_definition": "A declared target-excluded comparison cohort.",
            },
            value=value,
            unit=("households" if metric.endswith("household_count") else "proportion"),
            maximum_claim_type=ClaimType.DESCRIPTIVE,
        )
        for index, (metric, value) in enumerate(values.items(), start=1)
    )
    classification = EvidenceRecord(
        evidence_id="ev-peer-classification",
        run_id=RUN_ID,
        household_id="181",
        source_tool=ToolName.PEER_COMPARISON,
        source_tool_call_id=PEER_CALL_ID,
        metric="context_classification",
        dimensions={"target_excluded": "true"},
        text_value=ContextClassification.CUSTOMER_SPECIFIC.value,
        unit="classification",
        maximum_claim_type=ClaimType.ASSOCIATIONAL,
    )
    history = ToolHistoryEntry(
        decision_number=2,
        tool_name=ToolName.PEER_COMPARISON,
        normalized_signature="peer-signature",
        investigation_question="Is this decline unusual among comparison households?",
        decision_summary="Compute population and behavioral-peer context.",
        normalized_arguments={"household_id": "181", "peer_count": 5},
        attempts=(
            ToolAttemptRecord(
                attempt=1,
                tool_call_id=PEER_CALL_ID,
                status=ToolStatus.OK,
                elapsed_ms=4.0,
            ),
        ),
        final_status=ToolStatus.OK,
        evidence_ids=tuple(item.evidence_id for item in (*records, classification)),
    )
    state = outcome.state.model_copy(
        update={
            "tool_history": (*outcome.state.tool_history, history),
            "evidence_ledger": (
                *outcome.state.evidence_ledger,
                *records,
                classification,
            ),
        }
    )
    assert outcome.verification is not None and outcome.verification.final is not None
    verification = outcome.verification.model_copy(
        update={
            "final": outcome.verification.final.model_copy(
                update={
                    "confidence_adjustments": (
                        ConfidenceAdjustment(
                            context_classification=(
                                ContextClassification.INSUFFICIENT_CONTEXT
                            ),
                            maximum_confidence=ResolvedConfidence.MEDIUM,
                            reason=(
                                "The category comparison cohort is insufficient, "
                                "so the cited loss cannot receive high "
                                "customer-specific confidence."
                            ),
                        ),
                    )
                }
            )
        }
    )
    return outcome.model_copy(update={"state": state, "verification": verification})


def _outcome_with_conflicting_population_context() -> InvestigationOutcome:
    outcome = _outcome_with_population_context()
    broad_call_id = "call-report-peer-broad"
    broad_values = {
        "target_retailer_sales_change": -0.50,
        "population_household_count": 21.0,
        "population_median_retailer_sales_change": -0.45,
        "population_retailer_sales_change_q25": -0.60,
        "population_retailer_sales_change_q75": -0.30,
        "target_population_retailer_sales_change_percentile": 45.0,
        "population_declining_household_share": 0.80,
        "target_minus_population_median_change": -0.05,
        "peer_household_count": 5.0,
        "peer_median_retailer_sales_change": -0.48,
        "peer_retailer_sales_change_q25": -0.60,
        "peer_retailer_sales_change_q75": -0.35,
        "target_peer_retailer_sales_change_percentile": 40.0,
        "peer_declining_household_share": 0.80,
        "target_minus_peer_median_change": -0.02,
    }
    template_by_metric = {
        record.metric: record
        for record in outcome.state.evidence_ledger
        if record.source_tool_call_id == PEER_CALL_ID
    }
    broad_records = tuple(
        template_by_metric[metric].model_copy(
            update={
                "evidence_id": f"ev-peer-broad-{index:02d}",
                "source_tool_call_id": broad_call_id,
                "value": value,
            }
        )
        for index, (metric, value) in enumerate(broad_values.items(), start=1)
    )
    broad_classification = template_by_metric["context_classification"].model_copy(
        update={
            "evidence_id": "ev-peer-broad-classification",
            "source_tool_call_id": broad_call_id,
            "text_value": ContextClassification.BROAD_CONTEXT.value,
        }
    )
    original_history = outcome.state.tool_history[-1]
    broad_history = original_history.model_copy(
        update={
            "decision_number": 3,
            "normalized_signature": "peer-broad-signature",
            "attempts": (
                original_history.attempts[0].model_copy(
                    update={"tool_call_id": broad_call_id}
                ),
            ),
            "evidence_ids": tuple(
                record.evidence_id for record in (*broad_records, broad_classification)
            ),
        }
    )
    state = outcome.state.model_copy(
        update={
            "tool_history": (*outcome.state.tool_history, broad_history),
            "evidence_ledger": (
                *outcome.state.evidence_ledger,
                *broad_records,
                broad_classification,
            ),
        }
    )
    assert outcome.verification is not None and outcome.verification.final is not None
    existing_driver = outcome.verification.final.drivers[0]
    final = outcome.verification.final.model_copy(
        update={
            "drivers": (
                existing_driver.model_copy(
                    update={
                        "counterevidence_ids": (
                            *existing_driver.counterevidence_ids,
                            "ev-peer-broad-classification",
                        )
                    }
                ),
            ),
            "resolved_confidence": ResolvedConfidence.LOW,
            "counterevidence_ids": (
                *outcome.verification.final.counterevidence_ids,
                "ev-peer-broad-classification",
            ),
            "confidence_adjustments": (
                ConfidenceAdjustment(
                    context_classification=ContextClassification.BROAD_CONTEXT,
                    maximum_confidence=ResolvedConfidence.LOW,
                    reason=(
                        "The target resembles broad contemporaneous population and "
                        "peer movement, limiting confidence in a customer-specific "
                        "explanation."
                    ),
                    evidence_ids=(
                        "ev-peer-classification",
                        "ev-peer-broad-classification",
                    ),
                ),
                ConfidenceAdjustment(
                    context_classification=ContextClassification.INSUFFICIENT_CONTEXT,
                    maximum_confidence=ResolvedConfidence.MEDIUM,
                    reason=(
                        "The category comparison cohort is insufficient, so the "
                        "cited loss cannot receive high customer-specific confidence."
                    ),
                ),
            ),
        }
    )
    verification = outcome.verification.model_copy(update={"final": final})
    return outcome.model_copy(update={"state": state, "verification": verification})


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
    assert (
        report.population_context.context_classification
        is ContextClassification.INSUFFICIENT_CONTEXT
    )
    assert report.interpretation_limits.unobserved_factors
    assert report.likely_drivers[0].claim_type is ClaimType.ASSOCIATIONAL
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
        "Population and comparison context",
        "Investigation path",
        "Likely drivers",
        "Supporting evidence",
        "What this analysis can establish",
        "What this analysis cannot establish",
        "Unobserved factors and alternative explanations",
        "Counterevidence review",
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
    assert "\n## Counterevidence review\n" in markdown
    assert "\n- Alternative:" in markdown
    assert "Associational claim" in markdown
    assert "cannot establish" in markdown
    assert "hypothesis to test" in markdown
    assert "seasonal decline" not in markdown.casefold()


def test_population_context_values_are_rendered_only_from_bound_evidence() -> None:
    report = build_report_data(_outcome_with_population_context())

    assert (
        report.population_context.context_classification
        is ContextClassification.CUSTOMER_SPECIFIC
    )
    assert report.population_context.eligible_population.cohort_count == 20
    assert report.population_context.eligible_population.median_change == -0.10
    assert report.population_context.behavioral_peers.cohort_count == 5
    assert report.population_context.behavioral_peers.target_percentile == 0.0
    markdown = render_report_markdown(report)
    assert "Customer Specific" in markdown
    assert "-50.0%" in markdown
    assert "-10.0%" in markdown

    tampered = report.model_dump(mode="json")
    tampered["population_context"]["eligible_population"]["median_change"] = -0.11
    with pytest.raises(ValidationError, match="ledger metric"):
        type(report).model_validate(tampered)


def test_conflicting_context_calls_bind_values_to_conservative_classification() -> None:
    report = build_report_data(_outcome_with_conflicting_population_context())

    context = report.population_context
    assert context.context_classification is ContextClassification.BROAD_CONTEXT
    assert context.classification_evidence_id == "ev-peer-broad-classification"
    assert context.classification_evidence_ids == (
        "ev-peer-classification",
        "ev-peer-broad-classification",
    )
    assert context.eligible_population.cohort_count == 21
    assert context.eligible_population.median_change == -0.45
    assert all(
        evidence_id.startswith("ev-peer-broad-")
        for evidence_id in context.eligible_population.evidence_ids
    )

    cherry_picked = report.model_dump(mode="json")
    cherry_picked["population_context"]["context_classification"] = (
        ContextClassification.CUSTOMER_SPECIFIC.value
    )
    cherry_picked["population_context"]["classification_evidence_id"] = (
        "ev-peer-classification"
    )
    with pytest.raises(ValidationError, match="conservative classification"):
        type(report).model_validate(cherry_picked)


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

    fabricated_unavailable_count = report.model_dump(mode="json")
    fabricated_unavailable_count["population_context"]["eligible_population"][
        "cohort_count"
    ] = 999
    with pytest.raises(ValidationError, match="without evidence must be zero"):
        type(report).model_validate(fabricated_unavailable_count)

    missing_population_context = report.model_dump(mode="json")
    missing_population_context.pop("population_context")
    with pytest.raises(ValidationError, match="population_context"):
        type(report).model_validate(missing_population_context)

    missing_interpretation_object = report.model_dump(mode="json")
    missing_interpretation_object.pop("interpretation_limits")
    with pytest.raises(ValidationError, match="interpretation_limits"):
        type(report).model_validate(missing_interpretation_object)

    empty_interpretation_object = report.model_dump(mode="json")
    empty_interpretation_object["interpretation_limits"] = {}
    with pytest.raises(ValidationError, match="observed_scope"):
        type(report).model_validate(empty_interpretation_object)

    missing_action = report.model_dump(mode="json")
    missing_action["action"] = None
    with pytest.raises(ValidationError, match="completed report"):
        type(report).model_validate(missing_action)

    wrong_owner = report.model_dump(mode="json")
    wrong_owner["evidence_ledger"][0]["household_id"] = "different"
    with pytest.raises(ValidationError, match="belong"):
        type(report).model_validate(wrong_owner)

    missing_counter_review = report.model_dump(mode="json")
    missing_counter_review["likely_drivers"][0]["counterevidence_ids"] = []
    missing_counter_review["likely_drivers"][0][
        "no_material_counterevidence_reason"
    ] = None
    with pytest.raises(ValidationError, match="counterevidence"):
        type(report).model_validate(missing_counter_review)

    claim_above_evidence = report.model_dump(mode="json")
    claim_above_evidence["supporting_evidence"][0]["maximum_claim_type"] = (
        ClaimType.DESCRIPTIVE.value
    )
    claim_above_evidence["evidence_ledger"][0]["maximum_claim_type"] = (
        ClaimType.DESCRIPTIVE.value
    )
    with pytest.raises(ValidationError, match="exceeds"):
        type(report).model_validate(claim_above_evidence)

    missing_interpretation_limits = report.model_dump(mode="json")
    missing_interpretation_limits["interpretation_limits"]["observed_scope"] = []
    with pytest.raises(ValidationError, match="at least 1 item"):
        type(report).model_validate(missing_interpretation_limits)


def test_report_schema_recomputes_counterevidence_and_confidence_policy() -> None:
    customer_specific = build_report_data(_outcome_with_population_context())
    forged_high = customer_specific.model_dump(mode="json")
    forged_high["action"]["resolved_confidence"] = ResolvedConfidence.HIGH.value
    with pytest.raises(ValidationError, match="deterministic evidence cap"):
        type(customer_specific).model_validate(forged_high)

    broad = build_report_data(_outcome_with_conflicting_population_context())
    omitted_adjustment = broad.model_dump(mode="json")
    omitted_adjustment["action"]["confidence_adjustments"] = []
    omitted_adjustment["action"]["resolved_confidence"] = (
        ResolvedConfidence.MEDIUM.value
    )
    with pytest.raises(ValidationError, match="deterministic evidence policy"):
        type(broad).model_validate(omitted_adjustment)

    omitted_counter = broad.model_dump(mode="json")
    omitted_counter["likely_drivers"][0]["counterevidence_ids"] = [COUNTER_ID]
    with pytest.raises(ValidationError, match="material broad or mixed"):
        type(broad).model_validate(omitted_counter)


def test_category_context_requires_explicit_target_exclusion_provenance() -> None:
    report = build_report_data(_outcome())
    document = report.model_dump(mode="json")
    dimensions = {
        "department": "GROCERY",
        "product_category": "SOUP",
        "direction": "loss",
    }
    values: tuple[tuple[str, float | None, str | None], ...] = (
        ("category_percentage_change", -0.50, None),
        ("category_population_household_count", 20.0, None),
        ("category_population_median_change", -0.10, None),
        ("category_population_declining_share", 0.40, None),
        ("target_minus_category_population_median_change", -0.40, None),
        (
            "category_context_classification",
            None,
            ContextClassification.CUSTOMER_SPECIFIC.value,
        ),
    )
    category_records: list[dict[str, object]] = []
    for index, (metric, value, text_value) in enumerate(values, start=1):
        context_metric = metric != "category_percentage_change"
        category_records.append(
            {
                "evidence_id": f"ev-category-context-{index}",
                "run_id": str(RUN_ID),
                "household_id": "181",
                "role": "context",
                "source_tool": ToolName.CATEGORY_DECOMPOSITION.value,
                "source_tool_call_id": CALL_ID,
                "source_status": ToolStatus.PARTIAL.value,
                "metric": metric,
                "dimensions": {
                    **dimensions,
                    **({"target_excluded": "true"} if context_metric else {}),
                },
                "value": value,
                "text_value": text_value,
                "unit": "classification" if text_value else "ratio",
                "maximum_claim_type": (
                    ClaimType.ASSOCIATIONAL.value
                    if text_value
                    else ClaimType.DESCRIPTIVE.value
                ),
                "limitations": [],
                "query_hash": "category-context-query",
            }
        )
    document["evidence_ledger"].extend(category_records)
    evidence_ids = [item["evidence_id"] for item in category_records]
    classification_id = evidence_ids[-1]
    document["population_context"]["category_context"] = [
        {
            "department": "GROCERY",
            "product_category": "SOUP",
            "available": True,
            "target_change": -0.50,
            "comparison_household_count": 20,
            "population_median_change": -0.10,
            "declining_household_share": 0.40,
            "target_minus_population_median_change": -0.40,
            "context_classification": ContextClassification.CUSTOMER_SPECIFIC.value,
            "target_excluded": True,
            "evidence_ids": evidence_ids,
            "classification_evidence_id": classification_id,
            "classification_evidence_ids": [classification_id],
            "limitations": [],
        }
    ]

    validated = type(report).model_validate(document)
    assert validated.population_context.category_context[0].target_excluded

    hidden_category_context = json.loads(json.dumps(document))
    hidden_category_context["population_context"]["category_context"] = []
    with pytest.raises(ValidationError, match="every ledger classification"):
        type(report).model_validate(hidden_category_context)

    category_records[-1]["dimensions"].pop("target_excluded")
    with pytest.raises(ValidationError, match="target exclusion"):
        type(report).model_validate(document)


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
        "population-comparison-context",
        "investigation-path",
        "likely-drivers",
        "supporting-evidence",
        "what-analysis-can-establish",
        "what-analysis-cannot-establish",
        "unobserved-factors",
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
