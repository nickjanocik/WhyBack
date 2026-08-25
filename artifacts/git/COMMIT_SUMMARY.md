# WhyBack Git commit summary

This is a factual index of the implementation history on
`codex/whyback-build`. The Git log remains authoritative. Check descriptions
below are taken from the corresponding commit messages; they are not
retroactive claims that every historical check was rerun at every later
commit.

The implementation history through `76ac8de` was pushed to
`git@github.com:nickjanocik/WhyBack.git` without a force-push. The summary
itself belongs to the final reviewer-artifact commit, so it cannot include its
own hash.

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

## Final verification snapshot

The final quality gate started from a clean `76ac8de` tree and completed with
all 11 stages passing:

- Ruff formatting and linting passed.
- Pyright reported no errors.
- Pytest recorded 188 tests: 187 passed and the live OpenAI test was skipped
  because `OPENAI_API_KEY` was absent.
- Branch-aware coverage was 86.89%, above the required 85% threshold.
- Deterministic evaluations passed their scenario contracts.
- Demo, official no-key, and official Type A artifacts passed strict
  verification.

The machine record is
[`artifacts/tests/test_audit.json`](../tests/test_audit.json), with a readable
companion at [`artifacts/tests/TEST_AUDIT.md`](../tests/TEST_AUDIT.md). It
retains preliminary invocations as well as the final successful clean-tree
run, including an honestly recorded sandbox dependency-resolution failure.

## Publication notes

- Working branch: `codex/whyback-build`
- Remote repository: `https://github.com/nickjanocik/WhyBack.git`
- Protected/default branch changed directly: no
- Force-push used: no
- Live model execution claimed: no; it was skipped because no key was present
- Raw or prepared official data committed: no
