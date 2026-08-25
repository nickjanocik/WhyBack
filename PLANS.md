# WhyBack implementation plan

Status legend: **planned**, **implemented**, **verified**, **blocked**, or
**skipped**. A feature is not verified merely because code exists.

## Milestones and commit boundaries

Milestones 1–10 are the prior submission record. Their OpenAI/GPT terminology,
executed check counts, and skip status intentionally describe what was true at
that time; they are not current live-provider instructions.

| # | Milestone | Depends on | Acceptance and checks | Status |
|---|---|---|---|---|
| 1 | Project scaffold and guardrails | — | Naming, `src` layout, `uv` lock, CLI help, Ruff/Pyright/Pytest configuration, secret/data ignores, `AGENTS.md`; run scaffold tests and static checks | verified (2 tests; Ruff and Pyright clean) |
| 2 | Pinned data pipeline | 1 | Official commit URLs, SHA-256 verification, RDS/RDA normalization, contracts, canonical Parquet and manifest, idempotence, documented semantics; synthetic integration tests | verified (9 focused tests; full 22,627,890-row source preparation and idempotent reuse) |
| 3 | Decline detector | 2 | Max-week anchored 8+8 windows, eligibility, exact weighted score, deterministic ranking and 0.20/0.30/0.40 sensitivity; hand-calculated and property tests | verified (10 focused tests; full-data ranking found 304 flagged of 1,313 eligible) |
| 4 | Trend, category, and basket tools | 2–3 | Typed envelopes, deterministic metrics, `UNKNOWN` mapping, reconciliation, order invariance, no ad hoc data connections | verified (10 focused contract/tool/property tests; full-data smoke run) |
| 5 | Promotion, coupon, and peer tools | 2–4 | Unique promotion state and economic non-multiplication; Type A partial semantics; deterministic behavioral peers excluding target; invariant tests | verified (6 focused tests; full-data smoke run including a legitimate Type A partial case) |
| 6 | Bounded investigation workflow | 3–5 | Provider protocol, scripted and Responses backends, strict one-tool turns, explicit state, duplicate/turn/tool/retry/timeout bounds, fault injection, orchestration tests | verified (21 focused state/backend/orchestration/fault tests) |
| 7 | Evidence and governance | 6 | Immutable evidence ledger, catalog actions, confidence cap, ownership/failed-call/partial/reconciliation verifier checks, one repair attempt, unsupported-number rejection | verified (20 focused catalog/evidence/verifier tests) |
| 8 | Audit, reports, demo, and evals | 6–7 | Append-only JSONL, static trace and customer HTML, JSON/Markdown output, deterministic synthetic demo/failure example/golden trace, scenario metrics and artifact verifier | verified (five synthetic reports, persistent-failure and partial-data controls, six passing scenario contracts, and strict artifact verification) |
| 9 | Quality audit and CI | 1–8 | Unit/property/integration/orchestration coverage, branch-aware coverage target, machine-generated command audit, frozen CI without data/key/network dependencies | verified (complete gate PASS: 187 passed, one expected live-key skip, 86.89% branch coverage, all required artifact and evaluation checks passed) |
| 10 | Official data and reviewer docs | 2–9 | Full-data preparation and top-five deterministic selection where available; live GPT run only with a key; README compliance matrix, six ADRs, productionization, final red-team, commit summary | verified: official manifest v2 and Type A report pass strict verification; live GPT honestly skipped for absent key; independent red-team found no remaining core-code blocker; actual Git history summarized |
| 11 | Gemini live-provider migration | 6–10 | Replace the active provider with Gemini Interactions function calling; use `GEMINI_API_KEY`, backend `gemini`, default model `gemini-3.7-flash`, and `RETENTION_THINKING_LEVEL`; preserve legacy artifact reads; update tests and current docs | verified: clean-tree gate passed with 199 tests passed, one expected live-key skip, 87.17% branch-aware overall coverage, and all required artifact checks; live analytical-call contract passed |
| 12 | Population context and claim boundaries | 3–11 | Document the represented population and analytical limits; extend the existing peer and category tools with household-level contemporaneous context; type and verify claim strength; make reports and confidence context-aware; add deterministic scenarios and current artifacts | planned; baseline audit complete before implementation |

Each row is intended to become one coherent commit, with adjacent rows split or
combined only when it improves reviewability. Every commit must remain usable
and include only checks that actually passed.

## Milestone 12 baseline audit and gap table

The pre-change audit ran from clean commit `eed35ee` on
`codex/whyback-build`. The complete documented gate passed all 12 stages: 206
tests passed, one live-key test was skipped because `GEMINI_API_KEY` was absent,
and branch-aware overall coverage was 87.18% (633 of 846 branches covered).
The audit inspected the six tools, agent loop, evidence ledger, verifier,
confidence policy, report models and templates, evaluation suite, an official
customer report, and its execution trace before methodology changes began.

| Requirement | Existing status | Evidence in repo | Needed change |
|---|---|---|---|
| Dataset population documentation | Partial | `docs/data-semantics.md` documents source semantics, demographic missingness, retailer sales value, and observational limits; `README.md` says the detector is not causal | Expand the existing authoritative document with population, intended and inappropriate uses, selection/observability biases, observed and unobserved variables, controls, marketing-treatment confounding, and one-year temporal limits; link a concise README summary |
| Population-relative context | Partial | `src/whyback/tools/peer.py` deterministically excludes the target and returns peer median, IQR, and percentile; `src/whyback/tools/category.py` reconciles target-only category movement | Reuse those tools to add the full eligible household distribution, cohort sizes, declining share, target deviations, centralized context classification, and protected category cohorts with meaningful baseline activity |
| Claim-type enforcement | Partial | `src/whyback/agent/verifier.py` rejects numerical and causal free text and replaces model prose with governed templates; evidence ownership and source status are verified | Add typed descriptive/associational/causal claims, evidence support ceilings, per-driver counterevidence accounting, semantic causal-denial handling, and verifier tests; no current observational tool may support causal claims |
| Unobserved-factor reporting | Partial | Reports already include a limitations section plus one deterministic outside-retailer alternative and an uncertainty | Add populated structured interpretation limits, concise core and context-specific unobserved factors, explicit can/cannot-establish sections, and render them in JSON, Markdown, and HTML |
| Confidence adjustment | Partial | `FinalVerifier._confidence_cap` caps confidence by evidence breadth and propagated limitations | Incorporate deterministic population/category classification, treat missing context as a limitation rather than neutral evidence, cap customer-specific confidence under broad movement, and record adjustment reasons in the audit trace |

The minimal design keeps exactly six LLM-exposed tools, the application-owned
state, one-action turns, the immutable ledger, the governed action catalog, and
the single report pipeline. Population calculations remain deterministic and
are added to `peer_comparison`; reliable context for selected loss categories
is added to `category_decomposition`. The project uses the term **broad
contemporaneous context**, not proven seasonality.

## Detailed implementation sequence

### 1. Foundation

- Build Python 3.12 package metadata, console script, configuration, logging,
  Makefile, CI skeleton, and `.env.example`.
- Keep required runtime dependencies small; optional telemetry and MCP remain
  out unless the core gate is healthy and their value is demonstrable.
- Establish deterministic IDs/hashes and UTC timestamp conventions.

### 2. Data and semantics

- Fetch only `bradleyboehmke/completejourney` at
  `5b5d06192b9856edd04e4d405787af2f2e4a1fef`.
- Record every source and prepared SHA-256, schema, row count, missingness,
  preparation time/version, and derived-table definition.
- Normalize identifiers consistently; validate weeks 1–53, numeric measures,
  campaign types, promotion multiplicity, and metadata coverage.
- Prepare promotion state, household-week, basket, and product hierarchy tables
  where this avoids repeated expensive scans.

### 3. Analytics

- Implement the transparent decline formula without describing it as a churn
  probability.
- Implement exactly six registered tools with strict Pydantic input/output
  models and compact model summaries while preserving full results in traces.
- Make query provenance, rows examined, timing, cache state, source commit, and
  application version explicit.

### 4. Investigation and verification

- Let each fresh model decision choose one analytical tool or the finishing
  action from compact typed state.
- Enforce five analytical calls, about six decisions, exact duplicate refusal,
  timeout, and one retry only for retryable failures.
- Validate final evidence ownership and origin, partial limitations,
  counterevidence, approved action prerequisites, confidence cap, promotion and
  category invariants, and absence of free-form numerical claims.

### 5. Reviewer artifacts (prior submission plan)

- Generate deterministic synthetic reviewer artifacts in baseline CI.
- Attempt official full data acquisition and top-five runs independently of the
  missing live-model key. Never substitute synthetic output under a real label.
- Under the prior submission policy, if `OPENAI_API_KEY` remained absent, record
  live runs as skipped and provide the exact command; do not manufacture
  reports.

Prior submission execution record: all official source files were prepared
under a clean manifest v2 bound to WhyBack source-tree version `960c098`; the
detector selected households `5`, `181`, `423`, `472`, and `682`. The six tools
were smoke-tested against full prepared data, including a legitimate Type A
partial case for household `181`. `OPENAI_API_KEY` was absent, so live GPT-5.6
runs were skipped; scripted outputs retained an explicit execution-mode label.

Current Gemini migration record: the active provider has been changed to
Gemini, with backend `gemini`, default model `gemini-3.7-flash`, explicit
`GEMINI_API_KEY`, and `RETENTION_THINKING_LEVEL`. A synthetic live analytical
call returned a provider-issued function-call ID. A longer synthetic attempt
completed three decision/tool turns before the fourth provider request failed
at the configured 60-second request boundary and the application failed closed.
No completed live investigation or live customer artifact is claimed, and
official customer-behavior data was not sent to Gemini.

## Expected testing by layer

- Unit: hand-calculated windows, scoring, every tool, evidence, actions,
  confidence, verifier, renderers, contracts.
- Property: bounded scores/budgets, ordering and unrelated-household
  invariance, reconciliation, non-multiplication, peer exclusion, unique IDs,
  explicit empty-window statuses, invalid citations, partial limitations.
- Integration: synthetic Parquet → DuckDB → detector/tools → verified reports.
- Orchestration: scripted dynamic paths, malformed/invalid/duplicate decisions,
  Type A fallback, retry-once and persistent failure, budget exhaustion, repair.
- Golden: normalized required event fields/order, not incidental prose or time.
- Evaluations: behavioral and safety rates rather than exact model wording.
- Live: separately marked and automatically skipped without a key/full data.

## Environmental risks and fallbacks

| Risk | Current observation | Safe response |
|---|---|---|
| Python 3.12/`uv` unavailable | Resolved: locked Python 3.12 environment is present | CI and reviewers install from the frozen lock; record any acquisition blocker |
| Restricted network | Resolved for source acquisition after approved network access | Keep pinned URLs/hashes; never use unofficial data or require network in baseline CI |
| Full promotions memory | Resolved locally: 20,940,529 rows prepared and canonicalized once | Retain manifest/idempotence; prefer cancellable warehouse SQL in production |
| Prior OpenAI credential (historical) | `OPENAI_API_KEY` was unset for the prior submission | Preserve the skip record and its artifacts as historical evidence |
| Gemini credential and live validation | Synthetic analytical-call contract passed; a longer synthetic attempt later failed at the configured 60-second request boundary | Keep scripted tests as the baseline; claim contract validation only, and require separate authorization before transmitting official data |
| Empty remote | Resolved: milestone commits are on `origin/codex/whyback-build` | Continue on the approved branch and push without force |
| Optional ecosystem drift | MCP/telemetry APIs can change | Omit from core unless verified against current official APIs and isolated behind extras |

## Prior submission final artifact checklist

This completed checklist records the OpenAI-era submission and remains
unchanged as historical evidence.

- [x] Pinned data manifest and semantics/provenance documentation
- [x] Ranked candidates and threshold sensitivity
- [x] Six typed deterministic analytical tools
- [x] Bounded dynamic investigator and two backends
- [x] Immutable evidence ledger, catalog, confidence cap, verifier
- [x] Typed failures, retries, test-only fault injection, JSONL trace
- [x] Structured/Markdown/HTML reports and static trace viewer
- [x] Deterministic synthetic demo, persistent-failure demo, golden trace
- [x] Official top-five selection; live investigations explicitly skipped while
      `OPENAI_API_KEY` was absent
- [x] Legitimate official Type A missing-exposure report and trace for household 181
- [x] Scenario catalog and generated deterministic evaluation summary
- [x] Machine-generated JUnit, coverage JSON, test audit, and artifact checks
- [x] Frozen baseline CI implemented and complete local gate verified
- [x] README, architecture/reliability/evaluation/data docs, six ADRs,
      productionization notes
- [x] Actual Git history summary (independent red-team findings are resolved)
- [x] Final quality gate passed and captured
- [x] Branch clean; all possible commits pushed without force

## Current Gemini migration checklist

- [x] Active backend and commands use `gemini` and `GEMINI_API_KEY`
- [x] Default model is `gemini-3.7-flash`; thinking uses
      `RETENTION_THINKING_LEVEL`
- [x] Legacy OpenAI artifact provenance remains readable and historically labeled
- [x] ADR 007 records the provider migration and its boundaries
- [x] Bounded live synthetic failure artifact generated, verified, and labeled
- [x] Deterministic migration quality gate rerun and captured
- [x] Live Gemini analytical-call contract validated with a provider-issued call ID
- [ ] Completed live official-data artifacts generated with explicit authorization
- [x] Migration worktree clean and all possible commits pushed without force
