# ADR 007 — Use Gemini function calling

- **Status:** Accepted
- **Date:** 2026-08-24
- **Supersedes:** [ADR 001](001-own-the-agent-loop.md) for the live provider only

## Context

WhyBack originally used OpenAI Responses as its live decision provider. The
product now needs Gemini functionality instead, without changing the
application-owned state machine, deterministic analytical tools, evidence
ledger, verifier, action catalog, or audit semantics.

Google documents `google-genai` as its
[official production SDK](https://ai.google.dev/gemini-api/docs/libraries), the
[Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)
as supporting stateless requests with `store=false`, and
[`gemini-3.7-flash`](https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash)
as a stable model with function calling and configurable thinking levels.
Gemini [function calling](https://ai.google.dev/gemini-api/docs/function-calling)
can produce multiple calls, so provider-side tool selection alone does not
establish WhyBack's exactly-one-action invariant.

## Decision

WhyBack uses `GeminiFunctionCallingBackend` as its only live runtime provider.
Each decision is a fresh Gemini Interactions request with `store=False`, compact
typed application state, explicit closed function declarations, and function
calling mode `any` restricted to the currently allowed tools. The SDK is
configured for one total HTTP attempt so WhyBack's retry budget remains
application-owned. The adapter accepts exactly one function call and rejects
zero, multiple, unknown, malformed, or unoffered calls before the runner can
execute anything.

WhyBack deliberately supports `GEMINI_API_KEY` as its sole application
credential variable and passes it explicitly to the SDK. Google's
[API-key documentation](https://ai.google.dev/gemini-api/docs/api-key) also
recognizes `GOOGLE_API_KEY` and gives it precedence during environment-based
discovery when both are set; explicit application handling avoids that
ambiguity.

The default model is `gemini-3.7-flash`. `RETENTION_MODEL` can override it, and
`RETENTION_THINKING_LEVEL` selects `low`, `medium`, or `high`, defaulting to
`medium`. Thinking summaries are disabled; hidden reasoning is not exposed,
parsed, or recorded, and only the structured function-call step crosses the
backend boundary.

Historical `openai` and `live_openai` provenance values remain readable by the
report and artifact verifier so preserved audits do not become unverifiable.
There is no active OpenAI runtime backend or OpenAI package dependency.

Implementation and deterministic adapter tests alone do not establish a live
provider run. A synthetic live contract request did return one valid analytical
function call with a provider-issued ID. A longer synthetic investigation made
three valid live decisions before a later request failed at the configured
60-second request boundary. WhyBack therefore claims contract validation, not a
completed live investigation. No official customer-behavior data was sent to
Gemini. Stateless `store=False` responses can omit the interaction resource ID,
so the adapter falls back to the returned function-call step ID documented for
function results.

## Consequences

- Deterministic analytics, orchestration bounds, and verification policy remain
  provider-neutral and unchanged.
- Exactly-one-call enforcement is application-owned because the provider may
  emit parallel calls.
- The SDK makes one total HTTP attempt so WhyBack's bounded retry policy remains
  authoritative.
- Live traces use provider-issued Gemini interaction or function-call IDs and
  `live_gemini` provenance.
- The repository must test Gemini schema translation, response parsing,
  malformed cardinality, credential handling, and legacy artifact reads.
