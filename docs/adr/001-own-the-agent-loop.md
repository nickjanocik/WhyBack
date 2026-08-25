# ADR 001 — Own the agent loop

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

The assignment evaluates orchestration, tool dispatch, application state,
budgets, retries, failures, tracing, and grounding. Hiding those decisions behind
an agent framework would make the most important behavior harder to inspect and
test. WhyBack needs fresh model judgment after each deterministic result, but it
does not need a general workflow graph or multiple cooperating agents.

## Decision

WhyBack owns a small explicit `InvestigationRunner` and calls the OpenAI
Responses API directly through `OpenAIResponsesBackend`. The live backend uses
strict function schemas, required tool choice, disabled parallel calls, and
exactly one accepted function call. A provider-neutral `ModelBackend` protocol
also supports `ScriptedBackend`, which drives the same loop without credentials.

Typed application state—not provider history—is authoritative. Each decision is
a fresh request containing only the detector snapshot, compact completed-tool
and evidence summaries, limitations, open questions, and remaining budgets.
Programmatic Tool Calling is not used because the application must inspect and
persist every result before the next model judgment.

## Consequences

- Bounds, retries, duplicate refusal, repair, and tracing are visible in one
  reviewable implementation and deterministic tests.
- WhyBack avoids an Agents SDK or LangGraph runtime dependency and provider-
  specific state ownership.
- The project must maintain its own schema conversion, response parsing, and
  loop tests.
- Adding another model provider requires only the narrow backend protocol, not
  replacement of analytics, evidence, or policy.
