# ADR 003 — Evidence ledger

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

Prompt instructions alone cannot guarantee that a model will copy a metric
correctly, cite the right household, avoid failed output, or preserve a partial-
data caveat. Rendering model-authored numerical prose would make grounding
difficult to prove after the fact.

## Decision

Every meaningful tool value becomes an immutable `EvidenceRecord` with a unique
ID, run and household ownership, source tool/call, metric, dimensions, values,
units, limitations, and query hash. A ledger accepts records only from `ok` or
`partial` results after validating ownership and origin.

The finish schema contains qualitative conclusions and evidence IDs. The
deterministic verifier validates every reference and action prerequisite,
rejects numerical/causal free text, propagates used limitations, and caps
confidence. Report code resolves all displayed numbers from authoritative
detector/evidence values.

## Consequences

- A reviewer can trace each quantitative report claim to deterministic code and
  invocation provenance.
- Failed, missing, foreign, or invented evidence fails closed.
- Reports can be regenerated without trusting model wording.
- The state and report schemas are more explicit, and each tool must emit useful
  evidence granularity rather than only a prose summary.
