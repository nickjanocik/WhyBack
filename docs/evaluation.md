# Evaluation strategy

WhyBack evaluates calculations, orchestration behavior, and publication safety
separately. Exact model prose is not a correctness target, and an LLM judge is
not used as the source of truth.

## What the suite establishes

The deterministic baseline is designed to answer five questions:

1. **Are source-derived metrics correct?** Hand-calculated and property tests
   exercise windows, scores, tool outputs, joins, and reconciliation.
2. **Can the control loop fail safely?** Scripted decisions exercise the real
   runner's budgets, duplicate refusal, retries, timeouts, repair, and fallback.
3. **Can a result be published without unsupported claims?** Ledger and verifier
   tests attempt foreign, missing, failed, partial, numerical, causal, and
   policy-invalid citations.
4. **Do reviewer artifacts preserve those guarantees?** Strict report, trace,
   manifest, and hash checks validate the portable output boundary.
5. **Does customer-specific language survive contemporaneous comparison?**
   Population, peer, and category context cases check typed classifications,
   deterministic confidence caps, associational claim labels, and causal
   rejection without scoring model prose.

The suite does not establish that a recommended treatment causes retention,
that the decline score predicts churn, or that a live model will always choose
the optimal investigation path.

## Test layers

| Layer | Main purpose | Representative invariants |
| --- | --- | --- |
| Unit | Verify hand-calculated components and strict contracts | 8+8 windows, weighted score, tool metrics, campaign logic, confidence, rendering |
| Property | Search broad input spaces for invariant violations | Score bounds, row-order invariance, peer exclusion, reconciliation, economic non-multiplication, unique evidence IDs |
| Integration | Exercise real boundaries on synthetic prepared Parquet | Frames → normalization → derived tables → DuckDB repository → detector/tools |
| Orchestration | Exercise application state with `ScriptedBackend` | One action, budgets, duplicates, invalid arguments, retry once, persistent failure, finish repair, limitations |
| Golden | Detect regressions in stable trace structure | Required event fields and ordering after unstable IDs/times/latencies are normalized |
| Artifact | Validate portable reviewer outputs independently | Strict report schema, evidence references, trace lifecycle, execution-mode label, file hashes |
| Live | Check provider compatibility and model behavior | Explicitly marked; skipped without key/data; never required by baseline CI |

Baseline commands are:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python scripts/run_quality_gate.py
```

The quality-gate script is the only source for the final all-suite claim. It
captures exact commands, start/end timestamps, duration, exit code, output,
environment, dependency-lock and source-tree hashes, Git state, dataset
identity, JUnit, and branch-aware coverage. Failed preliminary attempts remain
in the machine record. `artifacts/tests/test_audit.json` is authoritative;
`TEST_AUDIT.md` is its human-readable rendering.

## Analytical properties

The highest-value properties protect economic integrity and ownership:

- decline scores remain within `[0, 1]`;
- transaction ordering and unrelated households do not alter target direct
  metrics;
- empty/missing windows become explicit statuses instead of arithmetic errors;
- category totals reconcile to direct retailer sales value;
- promotion enrichment cannot multiply transaction rows or retailer sales
  value;
- the target is never one of its behavioral peers;
- tool and run evidence IDs are unique;
- analytical execution budget never becomes negative;
- an exact normalized call executes at most once;
- missing or failed-call evidence cannot pass verification; and
- cited partial evidence retains its limitation.

Small hand-calculated fixtures complement property tests. Property tests are not
used as a substitute for checking exact expected values.

## Behavioral scenario catalog

`evals/scenarios.yaml` is versioned and contains exactly twelve baseline
archetypes:

| Scenario | Observable expectation |
| --- | --- |
| `frequency_decline` | Select trend or basket evidence; coupon analysis is not a mandatory detour. |
| `category_collapse` | Select category decomposition; peer comparison is not mandatory first. |
| `promotion_associated_decline` | Select promotion analysis and retain the availability-not-exposure semantics. |
| `ambiguous_peer_comparison` | Select behavioral peer context without demographic targeting. |
| `type_a_coupon_exposure_gap` | Observe a partial coupon result, continue analysis, and propagate the exact-delivery limitation. |
| `persistent_promotion_timeout` | Record initial and retry failure, stay within budget, cite no failed evidence, and finish from remaining evidence. |
| `broad_decline` | Classify target movement as broad context, cap confidence at low, and retain an associational verified driver. |
| `customer_specific_decline` | Classify the target as materially worse than stable population and peer movement, resolving confidence at medium without causal language. |
| `broad_category_decline` | Classify the cited category loss as broad, apply a low confidence cap, and retain an associational category driver. |
| `target_specific_category_decline` | Classify the cited category loss as customer-specific while preserving the observational claim boundary. |
| `insufficient_comparison_population` | Emit insufficient context, a medium confidence cap, and a propagated minimum-cohort limitation. |
| `causal_language_attack` | Reject a substantive causal finish with the typed `unsupported_causal_claim` code, then complete through bounded repair or safe fallback. |

Each scenario declares relevant tools, calls that must not be treated as
mandatory, required partial/failed tools, limitation or graceful-degradation
expectations, and maximum tool/decision counts. The contract is intentionally
about observable behavior rather than a hard-coded full sequence. Methodology
cases additionally declare exact context and resolved-confidence expectations,
expected verified claim types and Next Best Actions, population-percentile
availability, required broad-context warnings or confidence adjustments, and
required causal rejection as applicable.

## Deterministic metrics

`evals/run_evals.py` normalizes a completed `InvestigationOutcome`, an
`InvestigationState`, or a strict JSON run summary. It then reports transparent
numerator, denominator, and rate for:

- scenario contract pass;
- relevant tool selection;
- avoidance of irrelevant mandatory calls;
- analytical/decision budget compliance;
- final verification pass;
- evidence grounding;
- partial limitation propagation;
- graceful degradation after required failure;
- context classification;
- resolved confidence;
- application of the expected context-based confidence adjustment;
- verified claim type;
- verified Next Best Action;
- population-percentile availability where the scenario requires or forbids it;
- a typed broad-context warning carried by confidence adjustments;
- typed rejection of unsupported causality;
- duplicate calls; and
- unsupported evidence references.

Evidence grounding means every referenced ID exists in the ledger. Graceful
degradation additionally requires a non-failed, verified terminal result and
the expected failed tool. Applicability denominators are explicit, so a
limitation or failure metric cannot appear perfect merely because no relevant
scenario ran.

The scorer evaluates typed summaries and never invokes a model or judges prose.
`src/whyback/evaluation_cases.py` separately materializes the twelve scripted
cases through the real detector, runner, analytical tools, evidence ledger, and
verifier before normalization. Therefore, an evaluation artifact is meaningful
only with honest input provenance. Scripted executions, controlled contract
fixtures, and live model runs must be labeled distinctly.

For a file of normalized summaries:

```bash
uv run python -m evals.run_evals path/to/normalized_runs.json \
  --json-output artifacts/evals/eval_summary.json \
  --markdown-output artifacts/evals/EVAL_SUMMARY.md
```

## Failure-focused evaluation

The persistent promotion timeout is more useful than a success-only demo. It
must demonstrate the following event-level facts:

1. `promotion_response` is requested;
2. attempt one returns `retryable_error`;
3. exactly one `retry_scheduled` event appears;
4. attempt two returns `retryable_error`;
5. no promotion evidence is added;
6. the tool is no longer offered;
7. other valid tools can add evidence;
8. verification passes or produces explicit insufficiency; and
9. the report exposes the unavailable analysis and human-review requirement.

The one-time timeout case separately proves recovery without a second retry.
Fault injection is explicit and traces identify it as demo-only.

The causal-language attack is similarly end-to-end: it submits a causal
`DriverClaim` against observational trend evidence, requires the verifier's
machine-readable causal rejection, and observes the runner's single repair or
safe fallback. Passing depends on that rejection code and the verified terminal
state, not on matching a sentence or keyword in rendered prose.

## Official-data checks

The full official-data preparation and detector were executed locally. The
pinned source contained 22,627,890 rows across eight files and prepared ten
tables. Detector diagnostics found 1,313 eligible households and flagged 430,
304, and 202 at thresholds `0.20`, `0.30`, and `0.40`, respectively. The top
five IDs were `5`, `181`, `423`, `472`, and `682`.

All six tools were smoke-tested against the prepared source. A legitimate Type
A case was observed among the canonical top five: household `181` returned the
expected partial coupon semantics while retaining known participation and
redemption facts. Those checks establish compatibility with the full source;
the source manifest and generated artifacts are the proper provenance records.

## Live-model status

The preserved prior-submission artifacts record that the OpenAI Responses
backend was not run because `OPENAI_API_KEY` was absent. Live GPT-5.6
investigations were skipped rather than replaced with scripted output under a
live label. That remains truthful historical evidence and is not a current
provider-status claim.

The current live backend uses Gemini function calling through the Interactions
API. A live request over a fabricated decline snapshot returned a valid
analytical function call and provider-issued call ID. A longer synthetic run
completed three live decision/tool turns before a later provider request failed
at the configured 60-second request boundary and the run failed closed. No
completed live investigation result is claimed, no official customer-behavior
data was sent to Gemini, and baseline CI remains credential-free. See
[ADR 007](adr/007-use-gemini-function-calling.md) for the provider decision.
The verified synthetic failure bundle is available at
[`artifacts/live-gemini-synthetic-failure/`](../artifacts/live-gemini-synthetic-failure/).

To run a separately authorized official-data investigation:

```bash
export GEMINI_API_KEY="..."
export RETENTION_MODEL="gemini-3.7-flash"
export RETENTION_THINKING_LEVEL="medium"
uv run whyback demo --customers 5 --backend gemini
uv run whyback verify-artifacts artifacts/live
uv run python scripts/run_quality_gate.py
```

The resulting manifest and traces must show backend `gemini`, a live Gemini
execution mode, and provider-issued Gemini interaction or function-call IDs
before any live-result claim is made.

## Reading the results

A high deterministic pass rate means the observed runs satisfied the declared
selection, methodology, and safety contracts. It does not mean every selected
tool was the only defensible tool, nor that generated prose was identical. A
zero duplicate or unsupported-evidence rate is desirable. Context, confidence,
claim-type, causal-rejection, limitation, and graceful-degradation rates should
always be read with their applicable denominators.

When a production incident reveals a new unsafe path, reduce it to the smallest
deterministic fixture, add or extend a scenario contract, and require it in the
deployment gate. Historical failures should remain regression cases rather
than being removed when prompts or models change.
