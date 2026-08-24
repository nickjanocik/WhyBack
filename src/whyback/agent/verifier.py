"""Deterministic grounding, action, invariant, and confidence verification."""

from __future__ import annotations

import re
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
_CAUSAL_CLAIM = re.compile(
    r"\b(?:caused?|causes|will\s+retain|guarantees?|ensures?\s+retention)\b",
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
    matching = [record for record in permitted if record.metric in rule.metrics]
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


class FinalVerifier:
    """Reject unsupported model claims and resolve a governed final decision."""

    def __init__(self, catalog: ActionCatalog) -> None:
        self._catalog = catalog

    def verify(
        self,
        state: InvestigationState,
        proposal: FinishProposal,
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
            if _NUMERICAL_CLAIM.search(text):
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
            if action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
                if proposal.supporting_evidence_ids or proposal.driver_summary:
                    _append_issue(
                        issues,
                        VerificationIssueCode.INSUFFICIENT_ACTION_MISMATCH,
                        "INSUFFICIENT_EVIDENCE cannot carry supported drivers.",
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

        used_limitations: list[str] = []
        for record in referenced.values():
            used_limitations.extend(record.limitations)
            history = call_histories.get(record.source_tool_call_id)
            if history is not None and history.final_status is ToolStatus.PARTIAL:
                used_limitations.extend(history.limitations)
        propagated_limitations = _deduplicate(used_limitations)

        self._verify_tool_invariants(state, issues)
        if issues or action is None:
            return VerificationResult(passed=False, issues=tuple(issues))

        cap = _confidence_cap(supporting_records, propagated_limitations)
        if action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
            resolved = ResolvedConfidence.INSUFFICIENT
            cap_applied = True
        else:
            resolved, cap_applied = _cap_confidence(proposal.proposed_confidence, cap)
        final = VerifiedFinalDecision(
            drivers=proposal.driver_summary,
            proposed_confidence=proposal.proposed_confidence,
            resolved_confidence=resolved,
            confidence_cap_applied=cap_applied,
            supporting_evidence_ids=proposal.supporting_evidence_ids,
            counterevidence_ids=proposal.counterevidence_ids,
            next_best_action_id=action.action_id,
            action_description=action.description,
            rationale=proposal.rationale,
            alternative_explanations=proposal.alternative_explanations,
            uncertainties=proposal.uncertainties,
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
                    isinstance(peers, list) and state.household_id in peers
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
