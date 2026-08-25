# ADR 006 — Deliberate non-choices

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

WhyBack is evaluated primarily as a bounded, evidence-grounded agent harness.
Extra systems would need to improve that goal enough to justify their code,
dependencies, governance, and failure surface.

## Decision

The submission does not use:

- a learned churn classifier—the transparent score identifies investigation
  candidates and is not mislabeled as probability;
- RAG or a vector database—the evidence is structured, relational, and computed
  on demand rather than retrieved from unstructured text;
- Spark—the pinned data fits an efficient local DuckDB/Parquet workflow;
- multiple business agents—one investigator with deterministic policy is easier
  to bound, audit, and evaluate;
- Programmatic Tool Calling in the core loop—fresh application-mediated
  decisions ensure every result updates authoritative state before another
  action;
- automatic customer outreach—recommendations require human review, consent,
  and controlled measurement; or
- a heavy web frontend—static HTML reports and trace viewers satisfy local
  review without a deployed service.

LangChain and LangGraph are likewise unnecessary for this explicit loop.

## Consequences

- The architecture stays small enough to inspect end to end and keeps
  calculations, governance, and failures visible.
- The system does not claim predictive sophistication or automated campaign
  execution.
- Future additions must address a measured operational need while preserving
  evidence, bounds, verification, and human approval.
