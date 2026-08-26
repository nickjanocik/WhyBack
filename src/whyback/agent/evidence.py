"""Immutable evidence-ledger ownership and integrity checks."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from whyback.tools.contracts import SUCCESS_STATUSES, EvidenceRecord, ToolResult


class EvidenceLedgerError(ValueError):
    """A tool result attempted to add untrusted evidence to the ledger."""


class EvidenceLedger(BaseModel):
    """An immutable, append-only-in-use collection of deterministic records."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    records: tuple[EvidenceRecord, ...] = ()

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        """Reject a ledger containing the same evidence identifier twice."""

        identifiers = [record.evidence_id for record in self.records]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Evidence IDs must be unique within a ledger")
        return self

    @property
    def by_id(self) -> dict[str, EvidenceRecord]:
        """Return the ledger records keyed by their unique evidence IDs."""

        return {record.evidence_id: record for record in self.records}

    def add_tool_result(
        self,
        result: ToolResult,
        *,
        run_id: UUID,
        household_id: str,
    ) -> EvidenceLedger:
        """Return a new ledger after validating successful result ownership."""

        if result.status not in SUCCESS_STATUSES:
            if result.evidence:
                raise EvidenceLedgerError("Failed tool output cannot enter the ledger")
            return self

        existing = set(self.by_id)
        for record in result.evidence:
            if record.run_id != run_id:
                raise EvidenceLedgerError(
                    f"Evidence {record.evidence_id} belongs to another run"
                )
            if record.household_id != household_id:
                raise EvidenceLedgerError(
                    f"Evidence {record.evidence_id} belongs to another household"
                )
            if record.source_tool_call_id != result.tool_call_id:
                raise EvidenceLedgerError(
                    f"Evidence {record.evidence_id} has the wrong source call"
                )
            if record.evidence_id in existing:
                raise EvidenceLedgerError(
                    f"Evidence ID already exists in the run: {record.evidence_id}"
                )
            existing.add(record.evidence_id)
        return EvidenceLedger(records=(*self.records, *result.evidence))
