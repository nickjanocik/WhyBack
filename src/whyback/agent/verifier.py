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
    EvidencePrerequisite,
)
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishProposal,
    InvestigationState,
    ResolvedConfidence,
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
    COUNTEREVIDENCE_CONFLICT = "counterevidence_conflict"
    PEER_SELF_COMPARISON = "peer_self_comparison"
    CATEGORY_RECONCILIATION = "category_reconciliation"
    PROMOTION_MULTIPLICATION = "promotion_multiplication"
    INSUFFICIENT_ACTION_MISMATCH = "insufficient_action_mismatch"


class VerificationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: VerificationIssueCode
    message: str = Field(min_length=1)


class VerifiedFinalDecision(BaseModel):
    """A report-safe conclusion whose numeric content is resolved from evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    drivers: tuple[DriverClaim, ...]
    proposed_confidence: ConfidenceLevel
    resolved_confidence: ResolvedConfidence
    confidence_cap_applied: bool
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
    r"\b(?:caus(?:e|ed|es|ing)|drove|driven\s+by|because\s+of|due\s+to|"
    r"attribut(?:e|ed|es|ing)\s+to|explains?|explained\s+by|trigger(?:ed|s)?|"
    r"produc(?:e|ed|es|ing)|result(?:ed|s)?\s+from|resulting\s+from|led\s+to|"
    r"responsible\s+for|stems?\s+from|guarantee(?:d|s)?|ensures?|"
    r"(?:will|expected\s+to)\s+(?:boost|raise|grow|increase|improve|restore|retain|"
    r"reduce|prevent|decrease))\b",
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


def is_report_safe_qualitative(text: str) -> bool:
    """Reject model prose containing quantities, causality, guarantees, or exposure."""

    return not any(
        pattern.search(text)
        for pattern in (
            _NUMERICAL_CLAIM,
            _QUANTITATIVE_WORD_CLAIM,
            _CAUSAL_CLAIM,
            _EXPOSURE_CLAIM,
        )
    )


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


def _cap_confidence(
    proposed: ConfidenceLevel, cap: ResolvedConfidence
) -> tuple[ResolvedConfidence, bool]:
    proposed_resolved = _PROPOSED_TO_RESOLVED[proposed]
    if _CONFIDENCE_ORDER[proposed_resolved] <= _CONFIDENCE_ORDER[cap]:
        return proposed_resolved, False
    return cap, True


def _resolved_drivers(
    action: ActionDefinition,
    supporting_records: tuple[EvidenceRecord, ...],
) -> tuple[DriverClaim, ...]:
    template = _DRIVER_TEMPLATES.get(action.action_id)
    if template is None:
        return ()
    matching_ids = tuple(
        record.evidence_id
        for record in supporting_records
        if any(
            record.source_tool in rule.source_tools
            and record.metric in rule.metrics
            and any(predicate.matches(record) for predicate in rule.predicates)
            for rule in action.evidence_prerequisites
        )
    )
    if not matching_ids:
        return ()
    return (
        DriverClaim(
            summary=template,
            supporting_evidence_ids=matching_ids,
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

        for text in _free_text(proposal):
            if _NUMERICAL_CLAIM.search(text) or _QUANTITATIVE_WORD_CLAIM.search(text):
                _append_issue(
                    issues,
                    VerificationIssueCode.UNSUPPORTED_NUMERICAL_CLAIM,
                    "Free-form final text contains a raw numerical claim; reports must "
                    "resolve numbers from evidence IDs.",
                )
            if _CAUSAL_CLAIM.search(text):
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
        full_ledger_records = tuple(state.evidence_ledger)
        if action is not None:
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
                    narrower = tuple(
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
        propagated_limitations = _deduplicate(used_limitations)

        self._verify_tool_invariants(state, issues)
        if issues or action is None:
            return VerificationResult(passed=False, issues=tuple(issues))

        resolved_drivers = _resolved_drivers(action, supporting_records)
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
        cap = _confidence_cap(resolved_supporting_records, propagated_limitations)
        if action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
            resolved = ResolvedConfidence.INSUFFICIENT
            cap_applied = True
        else:
            resolved, cap_applied = _cap_confidence(proposal.proposed_confidence, cap)
        final = VerifiedFinalDecision(
            drivers=resolved_drivers,
            proposed_confidence=proposal.proposed_confidence,
            resolved_confidence=resolved,
            confidence_cap_applied=cap_applied,
            supporting_evidence_ids=resolved_supporting_ids,
            counterevidence_ids=proposal.counterevidence_ids,
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
