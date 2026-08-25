"""Deterministic grounding, action, invariant, and confidence verification."""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whyback.agent.actions import (
    ActionCatalog,
    ActionCatalogError,
    ActionDefinition,
    ActionId,
    EvidencePredicate,
    EvidencePrerequisite,
)
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishProposal,
    InvestigationState,
    ResolvedConfidence,
)
from whyback.methodology import (
    ClaimType,
    ContextClassification,
    resolve_context_classifications,
)
from whyback.tools.contracts import (
    SUCCESS_STATUSES,
    EvidenceRecord,
    ToolName,
    ToolStatus,
)


class VerificationIssueCode(StrEnum):
    """Stable machine-readable reasons a proposed result may be rejected."""

    UNKNOWN_EVIDENCE = "unknown_evidence"
    WRONG_EVIDENCE_OWNER = "wrong_evidence_owner"
    INVALID_EVIDENCE_SOURCE = "invalid_evidence_source"
    UNSUPPORTED_DRIVER = "unsupported_driver"
    ACTION_NOT_ALLOWED = "action_not_allowed"
    ACTION_PREREQUISITE = "action_prerequisite"
    ACTION_CONTRAINDICATION = "action_contraindication"
    UNSUPPORTED_NUMERICAL_CLAIM = "unsupported_numerical_claim"
    UNSUPPORTED_CAUSAL_CLAIM = "unsupported_causal_claim"
    CLAIM_STRENGTH_EXCEEDED = "claim_strength_exceeded"
    INVALID_CONTEXT_EVIDENCE = "invalid_context_evidence"
    COUNTEREVIDENCE_CONFLICT = "counterevidence_conflict"
    IRRELEVANT_COUNTEREVIDENCE = "irrelevant_counterevidence"
    MATERIAL_COUNTEREVIDENCE_OMITTED = "material_counterevidence_omitted"
    PEER_SELF_COMPARISON = "peer_self_comparison"
    CATEGORY_RECONCILIATION = "category_reconciliation"
    PROMOTION_MULTIPLICATION = "promotion_multiplication"
    INSUFFICIENT_ACTION_MISMATCH = "insufficient_action_mismatch"


class VerificationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: VerificationIssueCode
    message: str = Field(min_length=1)


class ConfidenceAdjustment(BaseModel):
    """One deterministic context-based maximum-confidence decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context_classification: ContextClassification
    maximum_confidence: ResolvedConfidence
    reason: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


class ConfidencePolicyResolution(BaseModel):
    """Deterministic confidence result reusable at runtime and artifact review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved_confidence: ResolvedConfidence
    confidence_cap_applied: bool
    confidence_adjustments: tuple[ConfidenceAdjustment, ...] = ()
    context_limitations: tuple[str, ...] = ()
    category_context_limitations: tuple[str, ...] = ()
    issues: tuple[VerificationIssue, ...] = ()


class VerifiedFinalDecision(BaseModel):
    """A report-safe conclusion whose numeric content is resolved from evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    drivers: tuple[DriverClaim, ...]
    proposed_confidence: ConfidenceLevel
    resolved_confidence: ResolvedConfidence
    confidence_cap_applied: bool
    confidence_adjustments: tuple[ConfidenceAdjustment, ...] = ()
    supporting_evidence_ids: tuple[str, ...]
    counterevidence_ids: tuple[str, ...]
    next_best_action_id: ActionId
    action_description: str
    rationale: str
    alternative_explanations: tuple[str, ...]
    uncertainties: tuple[str, ...]
    propagated_limitations: tuple[str, ...]
    human_review_required: Literal[True]
    recommended_success_metric: str
    suggested_experiment: str


class VerificationResult(BaseModel):
    """Complete deterministic verdict; failed verdicts cannot carry a final result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    issues: tuple[VerificationIssue, ...] = ()
    final: VerifiedFinalDecision | None = None

    @model_validator(mode="after")
    def validate_verdict(self) -> Self:
        if self.passed != (not self.issues and self.final is not None):
            raise ValueError("Verification verdict fields are inconsistent")
        return self


_NUMERICAL_CLAIM = re.compile(r"(?<![A-Za-z0-9_])(?:[$€£]\s*)?\d+(?:[.,]\d+)*(?:\s*%)?")
_QUANTITATIVE_WORD_CLAIM = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|dozen|hundred|thousand|million|billion|half|third|quarter|"
    r"twice|double|triple|percent|per\s+cent)\b",
    re.IGNORECASE,
)
_CAUSAL_CLAIM = re.compile(
    r"\b(?:caus(?:e|ed|es|ing)|drove|driven\s+by|because(?:\s+of)?|due\s+to|"
    r"owing\s+to|on\s+account\s+of|"
    r"attribut(?:e|ed|es|ing)\s+to|explains?|explained\s+by|trigger(?:ed|s)?|"
    r"produc(?:e|ed|es|ing)|result(?:ed|s)?\s+(?:from|in)|resulting\s+from|"
    r"contribut(?:e|ed|es|ing)\s+to|"
    r"(?:led|leads?|leading)\s+to|ma(?:de|kes?)\s+(?:the\s+)?"
    r"(?:customer|household)|"
    r"ma(?:de|kes?)\s+(?:them|him|her)\s+(?:decline|churn|leave|left|"
    r"disengage(?:d)?|stop(?:ped)?|reduce)|"
    r"(?:prompt|forc|push)(?:ed|es?)\s+(?:the\s+)?(?:customer|household|"
    r"decline|churn|disengagement)|brought\s+(?:about|on)|gave\s+rise\s+to|"
    r"(?:creat|spark)(?:e|ed|es|ing)\s+(?:the\s+)?(?:decline|churn|"
    r"disengagement)|induc(?:e|ed|es|ing)|account(?:ed|s|ing)?\s+for\s+"
    r"(?:(?:the\s+)?(?:customer|household)(?:'s)?\s+)?(?:the\s+)?"
    r"(?:decline|churn|disengagement)|"
    r"(?:arose|originat(?:e|ed|es|ing)|stems?|stemmed|stemming|"
    r"follow(?:ed|s|ing)?)\s+from|"
    r"(?:can|could|may|might)\s+be\s+traced\s+(?:back\s+)?to|"
    r"traceable\s+to|"
    r"(?:as\s+(?:a|the)?\s*|(?:is|are|was|were)\s+(?:a|the)\s+)"
    r"(?:direct\s+)?(?:consequence|result)\s+of|"
    r"(?:is|are|was|were)\s+(?:directly\s+)?behind\s+(?:the\s+)?"
    r"(?:decline|churn|disengagement)|"
    r"(?:is|are|was|were)\s+(?:the\s+)?"
    r"reason(?:\s+(?:for|that|why))?|(?:is|are|was|were)\s+why|"
    r"responsible\s+for|guarantee(?:d|s)?|ensures?|"
    r"(?:will|expected\s+to)\s+(?:boost|raise|grow|increase|improve|restore|retain|"
    r"reduce|prevent|decrease))\b",
    re.IGNORECASE,
)
_NEGATED_CAUSAL_PREFIX = re.compile(
    r"(?:\bcannot|\bcan\s+not|\bnot(?!\s+only\b))(?:\s+\w+){0,8}\s*$",
    re.IGNORECASE,
)
_UNCERTAIN_CAUSAL_PREFIX = re.compile(
    r"(?:\bno\s+(?:credible\s+)?evidence\s+(?:that|to\s+show\s+that|"
    r"(?:indicates?|shows?|supports?)(?:\s+that)?|"
    r"(?:(?!(?:but|however|yet|although|though|nevertheless)\b)"
    r"[\w'-]+\s+){0,12})|"
    r"\b(?:it\s+is\s+)?(?:unknown|unclear)\s+(?:whether|if))"
    r"(?:\s+[\w'-]+){0,12}\s*$",
    re.IGNORECASE,
)
_NEGATED_CAUSAL_SUFFIX = re.compile(
    r"^\s+(?:no\b|none\b|neither\b|not\s+(?!only\b)any\b)",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY = re.compile(
    r"(?:[.;!?]|\b(?:and|but|however|yet|although|though|nevertheless)\b)",
    re.IGNORECASE,
)
_EXPOSURE_CLAIM = re.compile(
    r"\b(?:household|customer)\s+(?:was|were|is)\s+exposed\b|"
    r"\breceived\s+(?:the|a)\s+(?:promotion|offer)\b|"
    r"\b(?:promotion|offer)\s+(?:reached|was\s+delivered\s+to)\s+(?:the\s+)?"
    r"(?:household|customer|shopper)\b|"
    r"\b(?:household|customer|shopper)\s+saw\s+(?:the|an?)\s+offer\b|"
    r"\b(?:household|customer|shopper)\s+(?:got|viewed|saw)\s+(?:the|an?)\s+"
    r"(?:promotion|offer)\b",
    re.IGNORECASE,
)
_CONFIDENCE_ORDER = {
    ResolvedConfidence.INSUFFICIENT: 0,
    ResolvedConfidence.LOW: 1,
    ResolvedConfidence.MEDIUM: 2,
    ResolvedConfidence.HIGH: 3,
}
_PROPOSED_TO_RESOLVED = {
    ConfidenceLevel.LOW: ResolvedConfidence.LOW,
    ConfidenceLevel.MEDIUM: ResolvedConfidence.MEDIUM,
    ConfidenceLevel.HIGH: ResolvedConfidence.HIGH,
}
_CLAIM_ORDER = {
    ClaimType.DESCRIPTIVE: 0,
    ClaimType.ASSOCIATIONAL: 1,
    ClaimType.CAUSAL: 2,
}
_CONTEXT_CLASSIFICATION_METRIC = "context_classification"
_CATEGORY_CONTEXT_CLASSIFICATION_METRIC = "category_context_classification"
_MISSING_CONTEXT_LIMITATION = (
    "Eligible-population and behavioral-peer context was not available; missing "
    "context must not be interpreted as neutral movement."
)
_OBSERVATIONAL_DRIVER_LIMITATION = (
    "The observational evidence supports an association, not a causal explanation "
    "of the household's behavior."
)
_MISSING_CATEGORY_CONTEXT_LIMITATION = (
    "Category-population context was unavailable for a cited category loss; missing "
    "category context must not be interpreted as customer-specific movement."
)
_DRIVER_TEMPLATES = {
    ActionId.CATEGORY_WINBACK: (
        "A recorded mapped category-level loss is a plausible contributor to the "
        "observed engagement decline."
    ),
    ActionId.VISIT_FREQUENCY_REACTIVATION: (
        "Reduced recorded visit cadence is a plausible contributor to the observed "
        "engagement decline."
    ),
    ActionId.PROMOTION_VALUE_REENGAGEMENT: (
        "A decline in recorded promotion-associated or coupon activity is a "
        "plausible contributor to the observed engagement decline."
    ),
    ActionId.PERSONALIZED_CHECK_IN: (
        "Multiple distinct computed behavioral measures support a multifactor "
        "engagement-decline hypothesis."
    ),
    ActionId.MONITOR: (
        "The recorded decline signal supports monitored reassessment while its "
        "underlying reason remains uncertain."
    ),
}
_DESCRIPTIVE_DRIVER_TEMPLATES = {
    ActionId.CATEGORY_WINBACK: (
        "A recorded mapped category-level loss is present in the observed decline."
    ),
    ActionId.VISIT_FREQUENCY_REACTIVATION: (
        "Recorded visit cadence declined during the observed period."
    ),
    ActionId.PROMOTION_VALUE_REENGAGEMENT: (
        "Recorded promotion-associated or coupon activity declined during the "
        "observed period."
    ),
    ActionId.PERSONALIZED_CHECK_IN: (
        "Multiple distinct computed behavioral measures changed during the observed "
        "period."
    ),
    ActionId.MONITOR: (
        "A recorded decline signal is present and warrants monitored reassessment; "
        "its underlying reason remains unknown."
    ),
}


def contains_unsupported_causal_claim(text: str) -> bool:
    """Return whether text contains a causal assertion rather than a denial."""

    for match in _CAUSAL_CLAIM.finditer(text):
        prefix = text[max(0, match.start() - 160) : match.start()]
        prefix = _CLAUSE_BOUNDARY.split(prefix)[-1]
        suffix = text[match.end() : match.end() + 40]
        if (
            _NEGATED_CAUSAL_PREFIX.search(prefix)
            or _UNCERTAIN_CAUSAL_PREFIX.search(prefix)
            or _NEGATED_CAUSAL_SUFFIX.search(suffix)
        ):
            continue
        return True
    return False


def is_report_safe_qualitative(text: str) -> bool:
    """Reject model prose containing quantities, causality, guarantees, or exposure."""

    return not any(
        pattern.search(text)
        for pattern in (
            _NUMERICAL_CLAIM,
            _QUANTITATIVE_WORD_CLAIM,
            _EXPOSURE_CLAIM,
        )
    ) and not contains_unsupported_causal_claim(text)


def _append_issue(
    issues: list[VerificationIssue],
    code: VerificationIssueCode,
    message: str,
) -> None:
    candidate = VerificationIssue(code=code, message=message)
    if candidate not in issues:
        issues.append(candidate)


def _deduplicate(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _free_text(proposal: FinishProposal) -> tuple[str, ...]:
    return (
        *(driver.summary for driver in proposal.driver_summary),
        *(
            driver.no_material_counterevidence_reason
            for driver in proposal.driver_summary
            if driver.no_material_counterevidence_reason is not None
        ),
        *(item for driver in proposal.driver_summary for item in driver.limitations),
        proposal.rationale,
        *proposal.alternative_explanations,
        *proposal.uncertainties,
    )


def _rule_satisfied(
    rule: EvidencePrerequisite, records: tuple[EvidenceRecord, ...]
) -> bool:
    permitted = [
        record for record in records if record.source_tool in rule.source_tools
    ]
    matching = [
        record
        for record in permitted
        if record.metric in rule.metrics
        and any(predicate.matches(record) for predicate in rule.predicates)
    ]
    if rule.metric_match == "all" and not set(rule.metrics).issubset(
        {record.metric for record in matching}
    ):
        return False
    if len(matching) < rule.minimum_matching_records:
        return False
    return (
        len({record.source_tool for record in matching}) >= rule.minimum_distinct_tools
    )


def _action_supported(
    action: ActionDefinition, records: tuple[EvidenceRecord, ...]
) -> bool:
    return any(_rule_satisfied(rule, records) for rule in action.evidence_prerequisites)


def _action_matching_records(
    action: ActionDefinition,
    records: tuple[EvidenceRecord, ...],
) -> tuple[EvidenceRecord, ...]:
    """Return records that satisfy an individual predicate for an action."""

    return tuple(
        record
        for record in records
        if any(
            record.source_tool in rule.source_tools
            and record.metric in rule.metrics
            and any(predicate.matches(record) for predicate in rule.predicates)
            for rule in action.evidence_prerequisites
        )
    )


def is_relevant_counterevidence(
    action: ActionDefinition,
    record: EvidenceRecord,
    supporting_records: tuple[EvidenceRecord, ...],
) -> bool:
    """Return whether a record deterministically qualifies the selected driver.

    A broad contemporaneous classification can qualify a customer-specific
    interpretation. Otherwise a counter must be an action-relevant measure that
    does not satisfy the action's adverse-direction predicate. Category counters
    must refer to a category present in the driver's support.
    """

    if record.metric == _CONTEXT_CLASSIFICATION_METRIC and record.text_value in {
        ContextClassification.BROAD_CONTEXT.value,
        ContextClassification.MIXED.value,
    }:
        return True
    if record.metric == _CATEGORY_CONTEXT_CLASSIFICATION_METRIC:
        if (
            action.action_id is not ActionId.CATEGORY_WINBACK
            or record.text_value
            not in {
                ContextClassification.BROAD_CONTEXT.value,
                ContextClassification.MIXED.value,
            }
        ):
            return False
        supported_categories = {
            (
                item.dimensions.get("department"),
                item.dimensions.get("product_category"),
            )
            for item in supporting_records
        }
        return (
            record.dimensions.get("department"),
            record.dimensions.get("product_category"),
        ) in supported_categories

    relevant_predicates = tuple(
        predicate
        for rule in action.evidence_prerequisites
        if record.source_tool in rule.source_tools and record.metric in rule.metrics
        for predicate in rule.predicates
        if predicate.metric == record.metric
    )
    if not any(
        _opposes_evidence_predicate(predicate, record)
        for predicate in relevant_predicates
    ):
        return False
    if action.action_id is not ActionId.CATEGORY_WINBACK:
        return True
    supported_categories = {
        (
            item.dimensions.get("department"),
            item.dimensions.get("product_category"),
        )
        for item in supporting_records
    }
    return (
        record.dimensions.get("department"),
        record.dimensions.get("product_category"),
    ) in supported_categories


def required_context_counterevidence_ids(
    action: ActionDefinition,
    supporting_records: tuple[EvidenceRecord, ...],
    full_ledger_records: tuple[EvidenceRecord, ...],
) -> tuple[str, ...]:
    """Return material broad or mixed context a driver must acknowledge.

    Category context is more specific than the run-wide population comparison, so
    a category action uses matching category classifications when they are
    available. Otherwise, broad or mixed run-wide context remains material. The
    function never manufactures a balancing record: it only requires already
    computed context that directly qualifies the cited action evidence.
    """

    material_values = (
        ContextClassification.BROAD_CONTEXT.value,
        ContextClassification.MIXED.value,
    )

    def canonical_material_id(
        records: Sequence[EvidenceRecord],
    ) -> str | None:
        for classification in material_values:
            for record in records:
                if record.text_value == classification:
                    return record.evidence_id
        return None

    if action.action_id is ActionId.CATEGORY_WINBACK:
        dimension_keys = ("department", "product_category", "direction")
        supported_categories = {
            tuple(record.dimensions.get(key) for key in dimension_keys)
            for record in _action_matching_records(action, supporting_records)
            if all(record.dimensions.get(key) is not None for key in dimension_keys)
        }
        records_by_category: dict[tuple[str | None, ...], list[EvidenceRecord]] = {}
        for record in full_ledger_records:
            category = tuple(record.dimensions.get(key) for key in dimension_keys)
            if (
                record.metric == _CATEGORY_CONTEXT_CLASSIFICATION_METRIC
                and category in supported_categories
            ):
                records_by_category.setdefault(category, []).append(record)
        category_context = tuple(
            evidence_id
            for records in records_by_category.values()
            if (evidence_id := canonical_material_id(records)) is not None
        )
        if category_context:
            return category_context

    global_context_id = canonical_material_id(
        tuple(
            record
            for record in full_ledger_records
            if record.metric == _CONTEXT_CLASSIFICATION_METRIC
        )
    )
    return (global_context_id,) if global_context_id is not None else ()


def _opposes_evidence_predicate(
    predicate: EvidencePredicate,
    record: EvidenceRecord,
) -> bool:
    """Require the same scope and the non-adverse side of an action threshold."""

    if record.metric != predicate.metric or not all(
        item.matches(record) for item in predicate.dimensions
    ):
        return False
    observed = getattr(record, predicate.field)
    if observed is None:
        return False
    opposites = {
        "lt": observed >= predicate.threshold,
        "lte": observed > predicate.threshold,
        "gt": observed <= predicate.threshold,
        "gte": observed < predicate.threshold,
        "eq": observed != predicate.threshold,
        "neq": observed == predicate.threshold,
    }
    return opposites[predicate.operator]


def _confidence_cap(
    records: tuple[EvidenceRecord, ...], limitations: tuple[str, ...]
) -> ResolvedConfidence:
    if not records:
        return ResolvedConfidence.INSUFFICIENT
    if (
        len(records) >= 2
        and len({record.source_tool for record in records}) >= 2
        and not limitations
    ):
        return ResolvedConfidence.HIGH
    return ResolvedConfidence.MEDIUM


def _lower_confidence_cap(
    left: ResolvedConfidence, right: ResolvedConfidence
) -> ResolvedConfidence:
    return left if _CONFIDENCE_ORDER[left] <= _CONFIDENCE_ORDER[right] else right


def _context_assessment(
    records: tuple[EvidenceRecord, ...],
    issues: list[VerificationIssue],
) -> tuple[ContextClassification, tuple[str, ...], tuple[str, ...]]:
    context_records = tuple(
        record for record in records if record.metric == _CONTEXT_CLASSIFICATION_METRIC
    )
    if not context_records:
        return (
            ContextClassification.INSUFFICIENT_CONTEXT,
            (),
            (_MISSING_CONTEXT_LIMITATION,),
        )

    classifications: list[ContextClassification] = []
    for record in context_records:
        if (
            record.source_tool is not ToolName.PEER_COMPARISON
            or record.dimensions.get("target_excluded") != "true"
        ):
            _append_issue(
                issues,
                VerificationIssueCode.INVALID_CONTEXT_EVIDENCE,
                "Population context classification lacks its required peer-tool "
                f"source or target-exclusion proof: {record.evidence_id}",
            )
        try:
            classifications.append(ContextClassification(record.text_value))
        except (TypeError, ValueError):
            _append_issue(
                issues,
                VerificationIssueCode.INVALID_CONTEXT_EVIDENCE,
                "Context classification evidence did not contain a recognized value: "
                f"{record.evidence_id}",
            )
    evidence_ids = tuple(record.evidence_id for record in context_records)
    limitations = _deduplicate(
        [item for record in context_records for item in record.limitations]
    )
    if not classifications:
        return (
            ContextClassification.INSUFFICIENT_CONTEXT,
            evidence_ids,
            (*limitations, _MISSING_CONTEXT_LIMITATION),
        )
    # Multiple bounded calls can create multiple classifications. Resolve conflicts
    # conservatively so a model cannot select the most favorable record.
    return (
        resolve_context_classifications(tuple(classifications)),
        evidence_ids,
        limitations,
    )


def _context_confidence_adjustments(
    classification: ContextClassification,
    evidence_ids: tuple[str, ...],
) -> tuple[ConfidenceAdjustment, ...]:
    if classification is ContextClassification.CUSTOMER_SPECIFIC:
        return ()
    if classification is ContextClassification.BROAD_CONTEXT:
        return (
            ConfidenceAdjustment(
                context_classification=classification,
                maximum_confidence=ResolvedConfidence.LOW,
                reason=(
                    "The target resembles broad contemporaneous population and peer "
                    "movement, limiting confidence in a customer-specific explanation."
                ),
                evidence_ids=evidence_ids,
            ),
        )
    if classification is ContextClassification.MIXED:
        reason = (
            "Population and peer context is mixed, so a uniquely customer-specific "
            "interpretation cannot receive high confidence."
        )
    else:
        reason = (
            "Population or peer context is insufficient, so missing comparison "
            "evidence cannot be treated as neutral."
        )
    return (
        ConfidenceAdjustment(
            context_classification=classification,
            maximum_confidence=ResolvedConfidence.MEDIUM,
            reason=reason,
            evidence_ids=evidence_ids,
        ),
    )


def _category_context_adjustments(
    action: ActionDefinition,
    supporting_records: tuple[EvidenceRecord, ...],
    full_ledger_records: tuple[EvidenceRecord, ...],
    issues: list[VerificationIssue],
) -> tuple[tuple[ConfidenceAdjustment, ...], tuple[str, ...]]:
    if action.action_id is not ActionId.CATEGORY_WINBACK:
        return (), ()

    dimension_keys = ("department", "product_category", "direction")
    cited_categories = {
        tuple(record.dimensions.get(key) for key in dimension_keys)
        for record in supporting_records
        if record.metric
        in {
            "category_retailer_sales_value",
            "contribution_to_lost_retailer_sales_value",
        }
        and all(record.dimensions.get(key) is not None for key in dimension_keys)
    }
    context_records = tuple(
        record
        for record in full_ledger_records
        if record.metric == _CATEGORY_CONTEXT_CLASSIFICATION_METRIC
        and tuple(record.dimensions.get(key) for key in dimension_keys)
        in cited_categories
    )
    covered_categories = {
        tuple(record.dimensions.get(key) for key in dimension_keys)
        for record in context_records
    }
    missing_categories = cited_categories.difference(covered_categories)

    classifications: list[ContextClassification] = []
    for record in context_records:
        if (
            record.source_tool is not ToolName.CATEGORY_DECOMPOSITION
            or record.dimensions.get("target_excluded") != "true"
        ):
            _append_issue(
                issues,
                VerificationIssueCode.INVALID_CONTEXT_EVIDENCE,
                "Category context classification lacks its required category-tool "
                f"source or target-exclusion proof: {record.evidence_id}",
            )
        try:
            classifications.append(ContextClassification(record.text_value))
        except (TypeError, ValueError):
            _append_issue(
                issues,
                VerificationIssueCode.INVALID_CONTEXT_EVIDENCE,
                "Category context evidence did not contain a recognized value: "
                f"{record.evidence_id}",
            )
    evidence_ids = tuple(record.evidence_id for record in context_records)
    limitations = _deduplicate(
        [item for record in context_records for item in record.limitations]
    )
    if missing_categories:
        classifications.append(ContextClassification.INSUFFICIENT_CONTEXT)
        limitations = _deduplicate([*limitations, _MISSING_CATEGORY_CONTEXT_LIMITATION])
    resolved = resolve_context_classifications(tuple(classifications))
    if resolved is ContextClassification.BROAD_CONTEXT:
        return (
            (
                ConfidenceAdjustment(
                    context_classification=ContextClassification.BROAD_CONTEXT,
                    maximum_confidence=ResolvedConfidence.LOW,
                    reason=(
                        "The cited category also declined broadly, so its movement is "
                        "not uniquely customer-specific."
                    ),
                    evidence_ids=evidence_ids,
                ),
            ),
            limitations,
        )
    if resolved is ContextClassification.INSUFFICIENT_CONTEXT:
        return (
            (
                ConfidenceAdjustment(
                    context_classification=(ContextClassification.INSUFFICIENT_CONTEXT),
                    maximum_confidence=ResolvedConfidence.MEDIUM,
                    reason=(
                        "The category comparison cohort is insufficient, so the cited "
                        "loss cannot receive high customer-specific confidence."
                    ),
                    evidence_ids=(() if missing_categories else evidence_ids),
                ),
            ),
            _deduplicate([*limitations, _MISSING_CATEGORY_CONTEXT_LIMITATION]),
        )
    if resolved is ContextClassification.MIXED:
        return (
            (
                ConfidenceAdjustment(
                    context_classification=ContextClassification.MIXED,
                    maximum_confidence=ResolvedConfidence.MEDIUM,
                    reason=(
                        "The cited category has mixed customer and broad movement, "
                        "limiting a uniquely customer-specific interpretation."
                    ),
                    evidence_ids=evidence_ids,
                ),
            ),
            limitations,
        )
    return (), limitations


def _cap_confidence(
    proposed: ConfidenceLevel, cap: ResolvedConfidence
) -> tuple[ResolvedConfidence, bool]:
    proposed_resolved = _PROPOSED_TO_RESOLVED[proposed]
    if _CONFIDENCE_ORDER[proposed_resolved] <= _CONFIDENCE_ORDER[cap]:
        return proposed_resolved, False
    return cap, True


def resolve_confidence_policy(
    *,
    action: ActionDefinition,
    proposed_confidence: ConfidenceLevel,
    proposal_supporting_records: tuple[EvidenceRecord, ...],
    resolved_supporting_records: tuple[EvidenceRecord, ...],
    full_ledger_records: tuple[EvidenceRecord, ...],
    support_limitations: tuple[str, ...],
) -> ConfidencePolicyResolution:
    """Recompute the complete evidence-owned confidence policy.

    Keeping this resolver independent of report or trace fields prevents a
    self-consistent but policy-invalid artifact from becoming authoritative.
    """

    issues: list[VerificationIssue] = []
    classification, evidence_ids, context_limitations = _context_assessment(
        full_ledger_records,
        issues,
    )
    adjustments = _context_confidence_adjustments(classification, evidence_ids)
    category_adjustments, category_context_limitations = _category_context_adjustments(
        action,
        proposal_supporting_records,
        full_ledger_records,
        issues,
    )
    adjustments = (*adjustments, *category_adjustments)
    cap = _confidence_cap(resolved_supporting_records, support_limitations)
    for adjustment in adjustments:
        cap = _lower_confidence_cap(cap, adjustment.maximum_confidence)
    if action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
        resolved = ResolvedConfidence.INSUFFICIENT
        cap_applied = True
    else:
        resolved, cap_applied = _cap_confidence(proposed_confidence, cap)
    return ConfidencePolicyResolution(
        resolved_confidence=resolved,
        confidence_cap_applied=cap_applied,
        confidence_adjustments=adjustments,
        context_limitations=context_limitations,
        category_context_limitations=category_context_limitations,
        issues=tuple(issues),
    )


def _resolved_drivers(
    action: ActionDefinition,
    supporting_records: tuple[EvidenceRecord, ...],
    proposal: FinishProposal,
) -> tuple[DriverClaim, ...]:
    matching_records = _action_matching_records(action, supporting_records)
    if not matching_records:
        return ()
    matching_ids = tuple(record.evidence_id for record in matching_records)
    matching_id_set = set(matching_ids)
    contributing_drivers = tuple(
        driver
        for driver in proposal.driver_summary
        if matching_id_set.intersection(driver.supporting_evidence_ids)
    )
    if not contributing_drivers:
        return ()
    claim_type = min(
        (
            *(record.maximum_claim_type for record in matching_records),
            *(driver.claim_type for driver in contributing_drivers),
        ),
        key=_CLAIM_ORDER.__getitem__,
    )
    templates = (
        _DESCRIPTIVE_DRIVER_TEMPLATES
        if claim_type is ClaimType.DESCRIPTIVE
        else _DRIVER_TEMPLATES
    )
    template = templates.get(action.action_id)
    if template is None:
        return ()
    limitations = _deduplicate(
        [
            _OBSERVATIONAL_DRIVER_LIMITATION,
            *(item for record in matching_records for item in record.limitations),
        ]
    )
    counterevidence_ids = _deduplicate(
        [
            evidence_id
            for driver in contributing_drivers
            for evidence_id in driver.counterevidence_ids
        ]
    )
    return (
        DriverClaim(
            summary=template,
            claim_type=claim_type,
            supporting_evidence_ids=matching_ids,
            counterevidence_ids=counterevidence_ids,
            no_material_counterevidence_reason=(
                None
                if counterevidence_ids
                else "No material counterevidence was cited from the available ledger."
            ),
            limitations=limitations,
        ),
    )


def _resolved_rationale(action_id: ActionId) -> str:
    if action_id is ActionId.INSUFFICIENT_EVIDENCE:
        return "Available verified evidence does not support a customer action."
    return (
        "The cited records satisfy the selected catalog action's machine-checkable "
        "evidence policy; the recommendation remains a human-reviewed test."
    )


class FinalVerifier:
    """Reject unsupported model claims and resolve a governed final decision."""

    def __init__(self, catalog: ActionCatalog) -> None:
        self._catalog = catalog

    def verify(
        self,
        state: InvestigationState,
        proposal: FinishProposal,
        *,
        allow_safe_fallback: bool = False,
    ) -> VerificationResult:
        issues: list[VerificationIssue] = []
        ledger = {record.evidence_id: record for record in state.evidence_ledger}
        referenced_ids = (
            *proposal.supporting_evidence_ids,
            *proposal.counterevidence_ids,
        )
        if set(proposal.supporting_evidence_ids).intersection(
            proposal.counterevidence_ids
        ):
            _append_issue(
                issues,
                VerificationIssueCode.COUNTEREVIDENCE_CONFLICT,
                "An evidence record cannot be both support and counterevidence.",
            )

        referenced: dict[str, EvidenceRecord] = {}
        for evidence_id in referenced_ids:
            record = ledger.get(evidence_id)
            if record is None:
                _append_issue(
                    issues,
                    VerificationIssueCode.UNKNOWN_EVIDENCE,
                    f"Referenced evidence does not exist: {evidence_id}",
                )
                continue
            referenced[evidence_id] = record
            if (
                record.run_id != state.run_id
                or record.household_id != state.household_id
            ):
                _append_issue(
                    issues,
                    VerificationIssueCode.WRONG_EVIDENCE_OWNER,
                    f"Evidence has the wrong run or household owner: {evidence_id}",
                )

        call_statuses = {
            attempt.tool_call_id: attempt.status
            for history in state.tool_history
            for attempt in history.attempts
        }
        call_histories = {
            attempt.tool_call_id: history
            for history in state.tool_history
            for attempt in history.attempts
        }
        for evidence_id, record in referenced.items():
            status = call_statuses.get(record.source_tool_call_id)
            if status not in SUCCESS_STATUSES:
                _append_issue(
                    issues,
                    VerificationIssueCode.INVALID_EVIDENCE_SOURCE,
                    "Evidence did not originate from a successful invocation: "
                    f"{evidence_id}",
                )

        full_ledger_records = tuple(state.evidence_ledger)
        methodology_context_records = tuple(
            record
            for record in full_ledger_records
            if record.metric
            in {
                _CONTEXT_CLASSIFICATION_METRIC,
                _CATEGORY_CONTEXT_CLASSIFICATION_METRIC,
            }
        )
        for record in methodology_context_records:
            if (
                record.run_id != state.run_id
                or record.household_id != state.household_id
            ):
                _append_issue(
                    issues,
                    VerificationIssueCode.WRONG_EVIDENCE_OWNER,
                    "Context evidence has the wrong run or household owner: "
                    f"{record.evidence_id}",
                )
            if call_statuses.get(record.source_tool_call_id) not in SUCCESS_STATUSES:
                _append_issue(
                    issues,
                    VerificationIssueCode.INVALID_EVIDENCE_SOURCE,
                    "Context evidence did not originate from a successful invocation: "
                    f"{record.evidence_id}",
                )
        context_classification, _, context_limitations = _context_assessment(
            full_ledger_records,
            issues,
        )

        support_id_set = set(proposal.supporting_evidence_ids)
        for driver in proposal.driver_summary:
            if not set(driver.supporting_evidence_ids).issubset(support_id_set):
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_DRIVER,
                    "Driver references evidence outside the support set: "
                    f"{driver.summary}",
                )
            if any(item not in ledger for item in driver.supporting_evidence_ids):
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_DRIVER,
                    f"Driver references missing evidence: {driver.summary}",
                )
            if driver.claim_type is ClaimType.CAUSAL:
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM,
                    "Current observational tools cannot support a causal driver claim.",
                )
            for evidence_id in driver.supporting_evidence_ids:
                record = ledger.get(evidence_id)
                if record is None:
                    continue
                if (
                    _CLAIM_ORDER[driver.claim_type]
                    > _CLAIM_ORDER[record.maximum_claim_type]
                ):
                    _append_issue(
                        issues,
                        VerificationIssueCode.CLAIM_STRENGTH_EXCEEDED,
                        "Driver claim strength exceeds its evidence ceiling: "
                        f"{evidence_id}",
                    )

        for text in _free_text(proposal):
            if _NUMERICAL_CLAIM.search(text) or _QUANTITATIVE_WORD_CLAIM.search(text):
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_NUMERICAL_CLAIM,
                    "Free-form final text contains a raw numerical claim; reports must "
                    "resolve numbers from evidence IDs.",
                )
            if contains_unsupported_causal_claim(text):
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM,
                    "Final text contains unsupported causal or guaranteed-retention "
                    "language.",
                )
            if _EXPOSURE_CLAIM.search(text):
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM,
                    "Final text claims household promotion exposure that availability "
                    "data cannot establish.",
                )

        try:
            action = self._catalog.get(proposal.next_best_action_id)
        except ActionCatalogError as error:
            _append_issue(
                issues,
                VerificationIssueCode.ACTION_NOT_ALLOWED,
                str(error),
            )
            action = None

        supporting_records = tuple(
            referenced[item]
            for item in proposal.supporting_evidence_ids
            if item in referenced
        )
        if action is not None:
            action_matching_ids = {
                record.evidence_id
                for record in _action_matching_records(action, supporting_records)
            }
            for driver in proposal.driver_summary:
                if not action_matching_ids.intersection(driver.supporting_evidence_ids):
                    continue
                driver_support = tuple(
                    ledger[evidence_id]
                    for evidence_id in driver.supporting_evidence_ids
                    if evidence_id in ledger
                )
                for evidence_id in driver.counterevidence_ids:
                    counter = ledger.get(evidence_id)
                    if counter is not None and not is_relevant_counterevidence(
                        action,
                        counter,
                        driver_support,
                    ):
                        _append_issue(
                            issues,
                            VerificationIssueCode.IRRELEVANT_COUNTEREVIDENCE,
                            "Driver counterevidence is not a deterministic qualifier "
                            f"for {action.action_id.value}: {evidence_id}",
                        )
                required_context_ids = set(
                    required_context_counterevidence_ids(
                        action,
                        driver_support,
                        full_ledger_records,
                    )
                )
                omitted_context_ids = required_context_ids.difference(
                    driver.counterevidence_ids
                )
                if omitted_context_ids:
                    _append_issue(
                        issues,
                        VerificationIssueCode.MATERIAL_COUNTEREVIDENCE_OMITTED,
                        "Driver omits material broad or mixed context: "
                        + ", ".join(sorted(omitted_context_ids)),
                    )
            if action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
                if proposal.supporting_evidence_ids or proposal.driver_summary:
                    _append_issue(
                        issues,
                        VerificationIssueCode.INSUFFICIENT_ACTION_MISMATCH,
                        "INSUFFICIENT_EVIDENCE cannot carry supported drivers.",
                    )
                supported_alternatives = tuple(
                    candidate.action_id
                    for candidate in self._catalog.actions
                    if candidate.action_id is not ActionId.INSUFFICIENT_EVIDENCE
                    and _action_supported(candidate, full_ledger_records)
                )
                if supported_alternatives and not allow_safe_fallback:
                    _append_issue(
                        issues,
                        VerificationIssueCode.ACTION_CONTRAINDICATION,
                        "INSUFFICIENT_EVIDENCE is contraindicated because the ledger "
                        "satisfies: "
                        + ", ".join(item.value for item in supported_alternatives),
                    )
            else:
                if not proposal.driver_summary or not supporting_records:
                    _append_issue(
                        issues,
                        VerificationIssueCode.UNSUPPORTED_DRIVER,
                        "A supported action requires at least one grounded driver.",
                    )
                if not _action_supported(action, supporting_records):
                    _append_issue(
                        issues,
                        VerificationIssueCode.ACTION_PREREQUISITE,
                        "Supporting evidence does not satisfy "
                        f"{action.action_id.value} prerequisites.",
                    )
                if action.action_id in {
                    ActionId.PERSONALIZED_CHECK_IN,
                    ActionId.MONITOR,
                }:
                    monitor_context_override = (
                        action.action_id is ActionId.MONITOR
                        and context_classification
                        in {
                            ContextClassification.BROAD_CONTEXT,
                            ContextClassification.INSUFFICIENT_CONTEXT,
                        }
                    )
                    narrower = (
                        ()
                        if monitor_context_override
                        else tuple(
                            candidate
                            for candidate_id in (
                                ActionId.CATEGORY_WINBACK,
                                ActionId.VISIT_FREQUENCY_REACTIVATION,
                                ActionId.PROMOTION_VALUE_REENGAGEMENT,
                            )
                            if _action_supported(
                                candidate := self._catalog.get(candidate_id),
                                full_ledger_records,
                            )
                        )
                    )
                    if narrower:
                        names = ", ".join(item.action_id.value for item in narrower)
                        _append_issue(
                            issues,
                            VerificationIssueCode.ACTION_CONTRAINDICATION,
                            f"{action.action_id.value} is contraindicated because "
                            f"the ledger satisfies narrower action policy: {names}.",
                        )
                if action.action_id is ActionId.CATEGORY_WINBACK:
                    unknown_loss = sum(
                        abs(record.change)
                        for record in full_ledger_records
                        if record.metric == "unknown_group_retailer_sales_value"
                        and record.change is not None
                        and record.change < 0
                    )
                    supported_known_loss = sum(
                        abs(record.change)
                        for record in supporting_records
                        if record.metric == "category_retailer_sales_value"
                        and record.change is not None
                        and record.change < 0
                    )
                    if unknown_loss > 0 and unknown_loss >= supported_known_loss:
                        _append_issue(
                            issues,
                            VerificationIssueCode.ACTION_CONTRAINDICATION,
                            "CATEGORY_WINBACK is contraindicated because unresolved "
                            "UNKNOWN loss equals or exceeds the cited mapped loss.",
                        )
                if action.action_id is ActionId.VISIT_FREQUENCY_REACTIVATION:
                    interval_metrics = {
                        "mean_basket_interval_days",
                        "median_basket_interval_days",
                    }
                    sparse_calls = {
                        record.source_tool_call_id
                        for record in supporting_records
                        if record.metric in interval_metrics
                    }
                    sparse = any(
                        history.final_status is ToolStatus.PARTIAL
                        and any(
                            "unavailable" in limitation.casefold()
                            or "at least two baskets" in limitation.casefold()
                            for limitation in history.limitations
                        )
                        for call_id, history in call_histories.items()
                        if call_id in sparse_calls
                    )
                    if sparse:
                        _append_issue(
                            issues,
                            VerificationIssueCode.ACTION_CONTRAINDICATION,
                            "VISIT_FREQUENCY_REACTIVATION is contraindicated because "
                            "a cited cadence window is missing.",
                        )

        category_context_limitations: tuple[str, ...] = ()
        if action is not None:
            _, category_context_limitations = _category_context_adjustments(
                action,
                supporting_records,
                full_ledger_records,
                issues,
            )

        used_limitations: list[str] = []
        for record in referenced.values():
            used_limitations.extend(record.limitations)
            history = call_histories.get(record.source_tool_call_id)
            if history is not None and history.final_status is ToolStatus.PARTIAL:
                used_limitations.extend(history.limitations)
        for history in state.tool_history:
            if history.tool_name not in state.unavailable_tools:
                continue
            used_limitations.append(
                f"{history.tool_name.value} is unavailable after its bounded retry "
                "policy was exhausted."
            )
            used_limitations.extend(history.limitations)
        support_limitations = _deduplicate(used_limitations)
        partial_result_limitations = _deduplicate(
            [
                *(
                    limitation
                    for history in state.tool_history
                    if history.final_status is ToolStatus.PARTIAL
                    for limitation in history.limitations
                ),
                *(
                    limitation
                    for record in full_ledger_records
                    if call_histories.get(record.source_tool_call_id) is not None
                    and call_histories[record.source_tool_call_id].final_status
                    is ToolStatus.PARTIAL
                    for limitation in record.limitations
                ),
            ]
        )
        propagated_limitations = _deduplicate(
            [
                *support_limitations,
                *partial_result_limitations,
                *context_limitations,
                *category_context_limitations,
            ]
        )

        self._verify_tool_invariants(state, issues)
        if issues or action is None:
            return VerificationResult(passed=False, issues=tuple(issues))

        resolved_drivers = _resolved_drivers(action, supporting_records, proposal)
        if (
            action.action_id is not ActionId.INSUFFICIENT_EVIDENCE
            and not resolved_drivers
        ):
            return VerificationResult(
                passed=False,
                issues=(
                    VerificationIssue(
                        code=VerificationIssueCode.UNSUPPORTED_DRIVER,
                        message=(
                            "No proposed driver maps the evidence that supports the "
                            "selected action."
                        ),
                    ),
                ),
            )
        resolved_supporting_ids = tuple(
            evidence_id
            for driver in resolved_drivers
            for evidence_id in driver.supporting_evidence_ids
        )
        resolved_supporting_records = tuple(
            referenced[evidence_id]
            for evidence_id in resolved_supporting_ids
            if evidence_id in referenced
        )
        resolved_counterevidence_ids = _deduplicate(
            [
                evidence_id
                for driver in resolved_drivers
                for evidence_id in driver.counterevidence_ids
            ]
        )
        confidence_policy = resolve_confidence_policy(
            action=action,
            proposed_confidence=proposal.proposed_confidence,
            proposal_supporting_records=supporting_records,
            resolved_supporting_records=resolved_supporting_records,
            full_ledger_records=full_ledger_records,
            support_limitations=support_limitations,
        )
        if confidence_policy.issues:
            return VerificationResult(
                passed=False,
                issues=confidence_policy.issues,
            )
        final = VerifiedFinalDecision(
            drivers=resolved_drivers,
            proposed_confidence=proposal.proposed_confidence,
            resolved_confidence=confidence_policy.resolved_confidence,
            confidence_cap_applied=confidence_policy.confidence_cap_applied,
            confidence_adjustments=confidence_policy.confidence_adjustments,
            supporting_evidence_ids=resolved_supporting_ids,
            counterevidence_ids=resolved_counterevidence_ids,
            next_best_action_id=action.action_id,
            action_description=action.description,
            rationale=_resolved_rationale(action.action_id),
            alternative_explanations=(
                "Recorded evidence does not distinguish the observed signal from "
                "unobserved activity outside this retailer.",
            ),
            uncertainties=(
                "Customer intent and activity outside the recorded retailer data "
                "are not observed.",
            ),
            propagated_limitations=propagated_limitations,
            human_review_required=True,
            recommended_success_metric=action.success_metric.description,
            suggested_experiment=action.experiment.description,
        )
        return VerificationResult(passed=True, final=final)

    @staticmethod
    def _verify_tool_invariants(
        state: InvestigationState, issues: list[VerificationIssue]
    ) -> None:
        for history in state.tool_history:
            if history.final_status not in SUCCESS_STATUSES:
                continue
            diagnostics = history.provenance_diagnostics
            if history.tool_name is ToolName.PEER_COMPARISON:
                peers = diagnostics.get("peer_household_ids", [])
                if diagnostics.get("target_excluded") is not True or (
                    isinstance(peers, Sequence)
                    and not isinstance(peers, str)
                    and state.household_id in peers
                ):
                    _append_issue(
                        issues,
                        VerificationIssueCode.PEER_SELF_COMPARISON,
                        "The target household appears in, or was not proven absent "
                        "from, its peer cohort.",
                    )
            elif history.tool_name is ToolName.CATEGORY_DECOMPOSITION:
                if (
                    diagnostics.get("baseline_reconciled") is not True
                    or diagnostics.get("recent_reconciled") is not True
                ):
                    _append_issue(
                        issues,
                        VerificationIssueCode.CATEGORY_RECONCILIATION,
                        "Category totals did not reconcile to transaction totals.",
                    )
            elif history.tool_name is ToolName.PROMOTION_RESPONSE:
                if (
                    diagnostics.get("row_count_preserved") is not True
                    or diagnostics.get("retailer_sales_value_preserved") is not True
                ):
                    _append_issue(
                        issues,
                        VerificationIssueCode.PROMOTION_MULTIPLICATION,
                        "Promotion enrichment did not preserve transaction count "
                        "and retailer sales value.",
                    )
