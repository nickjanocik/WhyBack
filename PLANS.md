# WhyBack implementation plan

Status legend: **planned**, **implemented**, **verified**, **blocked**, or
**skipped**. A feature is not verified merely because code exists.

## Milestones and commit boundaries

| # | Milestone | Depends on | Acceptance and checks | Status |
|---|---|---|---|---|
| 1 | Project scaffold and guardrails | — | Naming, `src` layout, `uv` lock, CLI help, Ruff/Pyright/Pytest configuration, secret/data ignores, `AGENTS.md`; run scaffold tests and static checks | verified (2 tests; Ruff and Pyright clean) |
| 2 | Pinned data pipeline | 1 | Official commit URLs, SHA-256 verification, RDS/RDA normalization, contracts, canonical Parquet and manifest, idempotence, documented semantics; synthetic integration tests | verified (9 focused tests; full 22,627,890-row source preparation and idempotent reuse) |
| 3 | Decline detector | 2 | Max-week anchored 8+8 windows, eligibility, exact weighted score, deterministic ranking and 0.20/0.30/0.40 sensitivity; hand-calculated and property tests | verified (10 focused tests; full-data ranking found 304 flagged of 1,313 eligible) |
| 4 | Trend, category, and basket tools | 2–3 | Typed envelopes, deterministic metrics, `UNKNOWN` mapping, reconciliation, order invariance, no ad hoc data connections | verified (10 focused contract/tool/property tests; full-data smoke run) |
| 5 | Promotion, coupon, and peer tools | 2–4 | Unique promotion state and economic non-multiplication; Type A partial semantics; deterministic behavioral peers excluding target; invariant tests | planned |
| 6 | Bounded investigation workflow | 3–5 | Provider protocol, scripted and Responses backends, strict one-tool turns, explicit state, duplicate/turn/tool/retry/timeout bounds, fault injection, orchestration tests | planned |
| 7 | Evidence and governance | 6 | Immutable evidence ledger, catalog actions, confidence cap, ownership/failed-call/partial/reconciliation verifier checks, one repair attempt, unsupported-number rejection | planned |
| 8 | Audit, reports, demo, and evals | 6–7 | Append-only JSONL, static trace and customer HTML, JSON/Markdown output, deterministic synthetic demo/failure example/golden trace, scenario metrics and artifact verifier | planned |
| 9 | Quality audit and CI | 1–8 | Unit/property/integration/orchestration coverage, branch-aware coverage target, machine-generated command audit, frozen CI without data/key/network dependencies | planned |
| 10 | Official data and reviewer docs | 2–9 | Full-data preparation and top-five deterministic selection where available; live GPT run only with a key; README compliance matrix, six ADRs, productionization, final red-team, commit summary | planned |

Each row is intended to become one coherent commit, with adjacent rows split or
combined only when it improves reviewability. Every commit must remain usable
and include only checks that actually passed.

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

### 5. Reviewer artifacts

- Generate deterministic synthetic reviewer artifacts in baseline CI.
- Attempt official full data acquisition and top-five runs independently of the
  missing live-model key. Never substitute synthetic output under a real label.
- If `OPENAI_API_KEY` remains absent, record live runs as skipped and provide the
  exact command; do not manufacture reports.

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
| Python 3.12/`uv` unavailable | System Python is 3.9.6 and `uv` initially absent | Install `uv` and let the pinned environment acquire 3.12; record any network blocker |
| Restricted network | Default shell cannot resolve GitHub | Request approved network access; pin URLs/hashes; never use unofficial data |
| Full promotions memory | Potentially large R object | Stream/convert once where possible; prefer local R/Arrow only if measured `pyreadr` failure occurs |
| OpenAI credential | `OPENAI_API_KEY` initially unset | Complete and verify scripted backend; mark live artifacts skipped with exact command |
| Empty remote | Unborn `main`, correct WhyBack origin | Work on `codex/whyback-build`, make coherent first commit, push only that branch |
| Optional ecosystem drift | MCP/telemetry APIs can change | Omit from core unless verified against current official APIs and isolated behind extras |

## Final artifact checklist

- [ ] Pinned data manifest and semantics/provenance documentation
- [ ] Ranked candidates and threshold sensitivity
- [ ] Six typed deterministic analytical tools
- [ ] Bounded dynamic investigator and two backends
- [ ] Immutable evidence ledger, catalog, confidence cap, verifier
- [ ] Typed failures, retries, test-only fault injection, JSONL trace
- [ ] Structured/Markdown/HTML reports and static trace viewer
- [ ] Deterministic synthetic demo, persistent-failure demo, golden trace
- [ ] Five official top-ranked investigations when data and credentials permit
- [ ] Type A missing-exposure example when a legitimate household is available
- [ ] Scenario evaluation summary
- [ ] Machine-generated JUnit, coverage JSON, test audit, and artifact check
- [ ] Frozen baseline CI
- [ ] README, architecture/reliability/evaluation/data docs, six ADRs,
      productionization notes
- [ ] Actual Git history summary and final independent red-team findings resolved
- [ ] Final quality gate passed and captured; branch clean; all possible commits
      pushed without force
