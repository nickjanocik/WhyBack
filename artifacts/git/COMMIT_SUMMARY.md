# WhyBack Git commit summary

This is a factual index of the implementation history on
`codex/whyback-build`. The Git log remains authoritative. Check descriptions
below are taken from the corresponding commit messages; they are not
retroactive claims that every historical check was rerun at every later
commit.

The implementation history through `211db13` was pushed to
`git@github.com:nickjanocik/WhyBack.git` without a force-push. The summary
itself belongs to the final bookkeeping commit, so it cannot include its own
hash.

| Commit | Plain-English subject | What the milestone established | Checks recorded by that commit | Remote state |
|---|---|---|---|---|
| `1b7be1c` | Set up the WhyBack project and developer tools | Product guardrails, package/CLI scaffold, locked environment, secret and data exclusions | Ruff, Pyright, 2 foundation tests | pushed |
| `5cf5e4c` | Add reproducible Complete Journey data preparation | Pinned verified downloads, canonical Parquet/DuckDB data, schema contracts, replayable manifest | Ruff, Pyright, 11 focused tests, 22,627,890-row full preparation, idempotent reuse | pushed |
| `a51cc94` | Add the customer decline detector | Anchored baseline/recent windows, eligibility, weighted scoring, stable ranking, sensitivity analysis | Ruff, Pyright, 19 focused tests, official-data detection smoke run | pushed |
| `3262d20` | Add customer trend, category, and basket analysis | Strict tool contracts, immutable evidence, deterministic trend/category/basket tools | Ruff, Pyright, 10 focused tests, official-data smoke run | pushed |
| `f65aad6` | Add promotion, coupon, and peer analysis | Completed six-tool registry with promotion invariants, coupon semantics, and target-excluding peers | Ruff, Pyright, 16 focused tests, official-data smoke run | pushed |
| `d2ae2bc` | Add typed investigation state and model backends | Immutable state, strict decision contracts, scripted and OpenAI Responses backends | Ruff, Pyright, 12 focused tests | pushed |
| `becf55b` | Add the bounded evidence-verified investigation loop | One-action loop, retry/turn/tool bounds, ledger, action catalog, verifier, safe fallback | Ruff, Pyright, 79 tests | pushed |
| `74e63c5` | Add failure injection and execution traces | Timeout controls and sanitized append-only lifecycle traces | Ruff, Pyright, 84 tests | pushed |
| `e24440f` | Add deterministic reports and trace viewer | Typed JSON/Markdown/HTML reports and an offline trace viewer | Ruff, Pyright, focused report/evaluation/demo/live-test selection | pushed |
| `19aaab7` | Add reproducible demos and behavioral evaluations | Scripted controls, five-customer reports, failure/Type A examples, six evaluation scenarios, strict artifact verification | Ruff, Pyright, focused report/evaluation/demo/live-test selection | pushed |
| `ce7c9e7` | Add deterministic quality gate and CI | Auditable frozen gate, JUnit/coverage/evaluation/artifact records, baseline CI, property checks | Ruff, Pyright, 123 passed and 1 credential-gated skip | pushed |
| `960c098` | Harden provenance, verification, and reviewer workflows | Strict provenance/lifecycle reconciliation, hardened failure boundaries, reviewer docs, packaging resources | Ruff, Pyright, 187 passed and 1 credential-gated skip, 86.88% coverage, wheel build | pushed |
| `76ac8de` | Generate verified reviewer artifacts and official controls | Five synthetic reports, persistent-failure evidence, official no-key status, official Type A control, machine-readable audit outputs | Complete gate, 187 passed and 1 credential-gated skip, 86.86% coverage, all three artifact profiles verified | pushed |
| `dac5232` | Publish the final audit and Git history | Clean-tree gate evidence, milestone history, and completed OpenAI-era reviewer checklist | Complete gate, 187 passed and 1 credential-gated skip, 86.89% coverage, all three artifact profiles verified | pushed |
| `a8b9a32` | Replace the live provider with Gemini | Stateless Gemini Interactions adapter, Gemini configuration/CLI/provenance, legacy artifact compatibility, and a labeled live synthetic request-boundary failure audit | Ruff, Pyright, 199 passed and 1 credential-gated skip, live analytical-call contract, live synthetic artifact verification | pushed |
| `4e0da21` | Harden the Gemini migration after audit | Compatible Interactions SDK floor, explicit function types, Gemini credential redaction/presence hardening, credential-independent historical verification, and corrected provider documentation | Ruff, Pyright, 206 passed and 1 credential-gated skip, 24 tests at the `google-genai==2.3.0` floor | pushed |
| `eed35ee` | Publish the final Gemini migration audit | Final provider-migration audit, clean-tree gate evidence, and package compatibility record | Complete gate, 206 passed and 1 credential-gated skip, 87.18% branch-aware coverage, four artifact profiles verified | pushed |
| `a30bac7` | Add interactive WhyBack investigator dashboard | Local React reviewer workspace and localhost-only artifact bridge without moving analytical authority out of Python | Dashboard check, localhost/security smoke, and focused accessibility audit | pushed |
| `462f50c` | Change dashboard development port to 5163 | Consistent dashboard port across Vite, bridge validation, tests, and docs | Dashboard check | pushed |
| `9c1df86` | Document the dataset population and analytical limits | Authoritative population, intended-use, bias, observability, confounding, and temporal-boundary documentation | Staged diff check | pushed |
| `2c38b5b` | Add population-relative decline context | Target-excluded eligible-population, behavioral-peer, and protected category distributions with centralized context classification | Ruff, Pyright, 13 focused tests | pushed |
| `d2b4359` | Enforce claim strength and causal guardrails | Typed claim ceilings, per-driver counterevidence, context-aware confidence, and causal/numerical prose rejection | Ruff, Pyright, 103 focused tests | pushed |
| `934484f` | Update reports, evaluations, and methodology checks | Structured methodology reports, exact trace reconstruction, 12 deterministic scenarios, and current documentation | Ruff, Pyright, 266 passed and 1 credential-gated skip | pushed |
| `4b2f89a` | Harden causal wording defenses | Expanded semantic causal assertions while preserving explicit non-causal denials | Ruff, Pyright, 100 focused tests | pushed |
| `ca54c81` | Close confidence and counterevidence trust gaps | Material-context citation requirements and independently recomputed confidence at runtime, report, and artifact boundaries | Ruff, Pyright, 286 passed and 1 credential-gated skip | pushed |
| `db6dbb0` | Extend causal language defenses | Additional idiomatic causal assertions blocked in final and public trace prose | Ruff, 117 focused tests | pushed |
| `bf7594e` | Scope causal denials to their clauses | Clause-aware negation plus pronoun and contribution attack coverage | Ruff, 124 focused tests | pushed |
| `d87a6cd` | Bind public artifacts to verified trace state | Exact report limitation/verifier-issue reconstruction, unsafe trace-prose checks, coordinated-tamper defenses, and migrated historical artifact | Ruff, 158 focused tests, four artifact profiles verified | pushed |
| `bac3b4e` | Require grounded report evidence partitions | Standalone report schema now requires grounded drivers, exact evidence partitions, and relevant counterevidence | Ruff, 45 focused tests | pushed |
| `211db13` | Publish verified methodology artifacts | Regenerated synthetic, evaluation, official Type A, and machine quality records for the settled methodology implementation | Complete gate, 309 passed and 1 credential-gated skip, 87.14% branch-aware coverage, four artifact profiles verified | pushed |

## Final verification snapshot

The final methodology quality gate ran from settled source commit `bac3b4e` as
invocation `bae4b901-5a31-4b17-bc60-897a368b93b3` and completed all 12 stages:

- Frozen dependency sync, Ruff formatting/linting, and Pyright passed.
- Pytest recorded 310 tests: 309 passed and the live Gemini test was skipped
  because `GEMINI_API_KEY` was deliberately absent.
- Branch-aware coverage was 87.14386211748153%: 920 of 1,206 branches and
  4,035 of 4,480 lines were covered, above the required 85% threshold.
- All 12 deterministic methodology scenario contracts passed, with no
  unsupported evidence citations across 26 evaluated citations.
- Demo, historical live Gemini bounded-failure, historical official no-key,
  and official Type A artifacts passed strict verification.
- The independent final red-team found no remaining high-severity issue; its
  causal-language, trace-prose, coordinated-tamper, and standalone-report
  findings were fixed and regression-tested before this gate.
- No live Gemini call ran during the gate, and official customer-behavior data
  was not transmitted to Gemini.

The machine record is
[`artifacts/tests/test_audit.json`](../tests/test_audit.json), with a readable
companion at [`artifacts/tests/TEST_AUDIT.md`](../tests/TEST_AUDIT.md). It
retains preliminary invocations as well as the final successful run, including
historical failures and skip reasons rather than rewriting them as successes.

## Publication notes

- Working branch: `codex/whyback-build`
- Remote repository: `https://github.com/nickjanocik/WhyBack.git`
- Protected/default branch changed directly: no
- Force-push used: no
- Live Gemini execution claimed: yes, narrowly; the analytical-call contract
  passed and a bounded synthetic run produced a verified failure artifact, but
  no completed live investigation is claimed
- Official-data live execution claimed: no; it was not attempted because
  transmitting official customer-behavior data requires separate explicit
  authorization
- Raw or prepared official data committed: no
