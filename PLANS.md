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
| 12 | Population context and claim boundaries | 3–11 | Document the represented population and analytical limits; extend the existing peer and category tools with household-level contemporaneous context; type and verify claim strength; make reports and confidence context-aware; add deterministic scenarios and current artifacts | verified: implementation, adversarial tests, 12 scenario contracts, regenerated synthetic and official Type A controls, strict artifact verification, and the complete credential-free gate passed |
| 13 | Literal assignment and documentation completion | 1–12 | Support the requested 3–4-customer exercise while retaining five committed results; explain every human-authored code boundary; bring root/web docs and the auditable gate in line with the dashboard; refresh exact official provenance | in progress: source, documentation, and targeted checks complete; official regeneration and final gate pending |

Each row is intended to become one coherent commit, with adjacent rows split or
combined only when it improves reviewability. Every commit must remain usable
and include only checks that actually passed.

## Milestone 12 baseline audit and gap table

The pre-change audit ran from clean commit `eed35ee` on
`codex/whyback-build`. The complete documented gate passed all 12 stages: 206
tests passed, one live-key test was skipped because `GEMINI_API_KEY` was absent,
and branch-aware overall coverage was 87.18% (633 of 846 branches covered).
The baseline gate invocation was `f8211cb7-5144-4d6f-8b72-7364dbb01ac9`.
The audit inspected the six tools, agent loop, evidence ledger, verifier,
confidence policy, report models and templates, evaluation suite, an official
customer report, and its execution trace before methodology changes began.

The word **Partial** in the next table is the historical status at `eed35ee`,
not current implementation debt. Every listed software gap is now verified.

| Requirement | Pre-change status | Baseline evidence | Gap identified at baseline | Current status |
|---|---|---|---|---|
| Dataset population documentation | Partial | `docs/data-semantics.md` documented source semantics, demographic missingness, retailer sales value, and observational limits; `README.md` said the detector was not causal | Expand the authoritative document with population, intended and inappropriate uses, selection/observability biases, observed and unobserved variables, controls, marketing-treatment confounding, and one-year temporal limits; link a concise README summary | Verified in `docs/data-semantics.md` and the README data-boundary summary |
| Population-relative context | Partial | `src/whyback/tools/peer.py` excluded the target and returned peer median, IQR, and percentile; `src/whyback/tools/category.py` reconciled target-only category movement | Reuse those tools to add the eligible-household distribution, cohort sizes, declining share, target deviations, centralized classification, and protected category cohorts with meaningful baseline activity | Verified in `src/whyback/methodology.py`, `peer.py`, `category.py`, and exact/exclusion tests |
| Claim-type enforcement | Partial | `src/whyback/agent/verifier.py` rejected numerical and selected causal free text; evidence ownership and source status were verified | Add typed descriptive/associational/causal claims, evidence support ceilings, per-driver counterevidence accounting, semantic causal-denial handling, and verifier tests | Verified at state, evidence, runtime-verifier, report-schema, and portable-artifact boundaries |
| Unobserved-factor reporting | Partial | Reports had a general limitations section plus one outside-retailer alternative and uncertainty | Add structured interpretation limits, concise core and context-specific unobserved factors, explicit can/cannot-establish sections, and render them in JSON, Markdown, and HTML | Verified in report models, renderers, templates, artifacts, and report tests |
| Confidence adjustment | Partial | `FinalVerifier._confidence_cap` capped confidence by evidence breadth and propagated limitations | Incorporate population/category classification, treat missing context as a limitation, cap customer-specific confidence under broad movement, and record reasons in the trace | Verified through shared deterministic confidence resolution at runtime, report, and artifact boundaries |

The minimal design keeps exactly six LLM-exposed tools, the application-owned
state, one-action turns, the immutable ledger, the governed action catalog, and
the single report pipeline. Population calculations remain deterministic and
are added to `peer_comparison`; reliable context for selected loss categories
is added to `category_decomposition`. The project uses the term **broad
contemporaneous context**, not proven seasonality.

## Milestone 12 verification record

The completed upgrade preserves all six analytical tools and the bounded
orchestrator. It adds deterministic, target-excluded household and category
comparison evidence; centralized `CUSTOMER_SPECIFIC`, `MIXED`,
`BROAD_CONTEXT`, and `INSUFFICIENT_CONTEXT` rules; descriptive and
associational claim ceilings; material counterevidence accounting; exact
confidence resolution; causal-language defense in depth; and structured
observed, unobserved, and causal boundaries in every report.

The latest credential-free gate ran from source commit `b2f5156` as invocation
`5aa9cf8c-3d51-4026-9850-fc1e91143c77`; all 12 stages passed. Pytest recorded
310 passes and one expected live-key skip, with 87.13% branch-aware coverage
(919 of 1,206 branches). The record is in
`artifacts/tests/test_audit.json`. Deterministic evaluations cover 12 scenario
contracts, including broad and customer-specific population and category
movement, insufficient cohorts, and a causal-language attack.
The synthetic demo, historical bounded Gemini failure, historical official
no-key record, and official Type A scripted control are verified separately.
No completed live Gemini investigation is claimed, and official customer data
was not transmitted to Gemini.

### Milestone 12 completion checklist

- [x] Existing architecture audited and reused without adding an analytical tool
- [x] Population, intended use, observability biases, controls, confounding, and
      one-year limits documented in `docs/data-semantics.md`
- [x] Target-excluded eligible-population, behavioral-peer, and protected
      category comparison cohorts implemented deterministically
- [x] Broad contemporaneous context affects confidence without being called
      proven seasonality or a specific cause
- [x] Claim types, evidence support ceilings, counterevidence, and deterministic
      confidence adjustments verified at runtime and artifact boundaries
- [x] Reports render population context, claim strength, unobserved factors,
      causal limits, and a human-reviewed measurement plan
- [x] Unit, property, orchestration, reporting, artifact-tamper, and deterministic
      evaluation regressions added
- [x] Reviewer artifacts regenerated and all four artifact profiles verified
- [x] Live Gemini execution skipped in the final gate because no environment
      credential was present; no live or official-data success was fabricated

## Current completion boundaries

All locally implementable methodology requirements are complete. Runtime words
such as `partial`, `missing_data`, `failed`, and `skipped` describe the quality
or availability of evidence for a particular run; they are not TODO markers.
Changing them to `ok` without new evidence would weaken WhyBack's fail-closed
contract.

| Current boundary | Why it remains limited | What would actually complete it |
|---|---|---|
| Synthetic peer calls return `partial` | The compact fixture has 23 eligible target-excluded peers while the tool requested 50. The result remains usable because the reliability minimum is five, but the unmet request is disclosed. | A genuinely larger fixture or source cohort; lowering the request merely to obtain `ok` would hide the limitation. |
| Official Type A coupon evidence is `partial` | The source provides a campaign pool but not the household-specific identities of the 16 delivered coupons. | The absent household delivery log from the source owner. |
| Some official trend/basket fields are `partial` or `missing_data` | A household with no recent transactions has no recent per-trip or basket-structure facts to compute; source weeks 1 and 53 are also shorter calendar weeks. | Additional observed transactions or corrected/full-period source coverage, never imputation presented as observation. |
| Completed live Gemini investigation | The final gate deliberately had no environment credential; the historical synthetic live run failed closed at its request boundary. | A fresh securely injected credential and a separately authorized synthetic run. |
| Completed live official-data investigation | Sending official household behavior to an external model was not authorized. | Explicit data-transmission authorization plus a fresh securely injected credential. |
| Recurring seasonality | Roughly one year cannot demonstrate a recurring annual pattern. | Comparable multi-year history; current reports correctly use broad contemporaneous context. |
| Customer motive, competitor activity, and person-level behavior | Complete Journey observes one retailer's household-level records, not intent, other channels, or individual household members. | New linked operational, survey, omnichannel, competitor, or person-level data with appropriate governance. |
| Causal treatment effects | Marketing treatment is observational and may be targeted from prior behavior. | A prospective randomized holdout or another separately justified causal design. |

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
- [x] Live official-data execution remains explicitly unclaimed and gated behind
      separate authorization and a fresh securely injected credential
- [x] Migration worktree clean and all possible commits pushed without force
