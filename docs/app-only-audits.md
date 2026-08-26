# Standalone Application Audits

WhyBack includes two post-hoc, read-only audit tools for reviewing application
behavior. They do not call Gemini, alter prepared data, participate in decline
detection or investigation, change an action, contact a customer, or extend a
verified artifact manifest. Their only optional write is an explicitly requested
JSON output file.

Write audit outputs to a separate location such as `artifacts/local/audits/`.
Never place them inside `data/prepared/` or an input artifact collection because
those directories have independent integrity contracts.

## Fairness monitoring

Run detector-stage monitoring with the validated prepared data:

```bash
uv run python scripts/audit_fairness.py \
  --prepared-dir data/prepared \
  --json-output artifacts/local/audits/fairness-detector.json
```

Add a verified investigation batch to audit its selection and terminal outcomes:

```bash
uv run python scripts/audit_fairness.py \
  --prepared-dir data/prepared \
  --artifact-root artifacts/local/live-runs/<collection> \
  --json-output artifacts/local/audits/fairness-full.json
```

Omit `--json-output` to print JSON to standard output. Repeat `--attribute` to
select from the fixed allowlist: `age`, `income`, `home_ownership`,
`marital_status`, `household_size`, `household_comp`, and `kids_count`. Without
that option, every allowlisted field present in the prepared table is audited.
`--minimum-group-size` defaults to 20 and cannot be lowered.

The prepared-data repository validates the source manifest and table hashes. If
an artifact root is supplied, the existing artifact verifier runs first, source
identity and detector counts are reconciled, and strict report models determine
the terminal memberships. The detector is recomputed with the artifact's policy
and analysis-window widths. Missing or skipped artifact outcomes are reported as
unavailable, never treated as failures or zeros.

| Stage | Numerator | Denominator |
| --- | --- | --- |
| `eligibility` | Detector-eligible households | Observed households |
| `flagging` | Households above the decline threshold | Eligible households |
| `selection` | Households selected for investigation | Flagged households |
| `completed` | Verified supported outcomes | Selected households |
| `insufficient_evidence` | Governed fallback outcomes | Selected households |
| `failed` | Runs without a publishable result | Selected households |
| `governed_action` | Supported non-fallback actions | Selected households |

The output has two privacy boundaries:

- Missing demographic rows, nulls, and blanks remain explicit as `UNKNOWN`.
- A non-`UNKNOWN` label represented by fewer than 20 observed households is
  combined into `SUPPRESSED`, so a rare label itself is not published.
- At each stage, a group denominator below 20 becomes `insufficient_sample`.
  Its numerator, denominator, rate, gap, and ratio are all `null`.
- If one positive stage cell is below 20, every peer cell for that stage is also
  withheld. This complementary suppression prevents recovery by subtraction.
- Coverage subcounts and the coverage rate are likewise all withheld when any
  positive known, unknown, missing-row, or missing-value cell is below 20.
- Attributes are evaluated separately. The audit publishes no intersections or
  household-level rows.

For a publishable group, the rate gap is the group rate minus the overall stage
rate, and the rate ratio is the group rate divided by that overall rate. A zero
overall rate leaves the ratio undefined. `review_recommended` is true only when
the absolute gap is at least 0.10 **and** the ratio is outside the inclusive
neutral interval `[0.80, 1.25]`. These are screening heuristics, not statistical
significance tests, fairness certifications, or legal conclusions.

The versioned JSON includes disclosure-controlled coverage, stage rates,
detector policy, exact week bounds, source and artifact manifest digests,
dataset identity, and the artifact backend and execution mode when available.
Artifact outcomes must name the exact prepared-manifest digest before they can
be joined to demographics. The output contains no
household, run, provider-call, or collection identifiers. Review flags and
honest unavailable stages still exit successfully; malformed, unverified, or
incompatible inputs return a nonzero exit code.

## Operational health and drift

Summarize one recursive artifact root or one explicit `trace.jsonl`:

```bash
uv run python scripts/audit_operations.py summarize ARTIFACT_ROOT \
  --json-output artifacts/local/audits/operations.json
```

Compare two compatible cohorts:

```bash
uv run python scripts/audit_operations.py compare BASELINE_ROOT CURRENT_ROOT \
  --minimum-runs 20 \
  --distance-threshold 0.20 \
  --require-assessment \
  --json-output artifacts/local/audits/drift.json
```

Each run directory discovered from either a report or a trace must contain a
regular `trace.jsonl` and sibling `report.json`. The loader validates both
schemas, a single start and terminal event, monotonic timestamps, consistent
private ownership, sequential model/tool/verification events, terminal status,
and recorded provenance. Duplicate run identities and malformed pairs are
excluded with content-derived short references rather than paths or identifiers.

| Input status | Meaning |
| --- | --- |
| `ready` | Every discovered pair is valid and shares one compatibility key |
| `partial` | At least one valid pair remains, but another pair was excluded |
| `invalid` | No valid pair can be summarized |
| `mixed_cohort` | Valid pairs contain more than one compatibility key |

Health output includes run status and action distributions; fingerprinted
application-version counts; run duration; model request, rejection, latency, and
recorded input/output token summaries; tool attempts, retries, status, latency,
and rows examined;
verification rejection codes; evidence counts; deterministic fallback; and
per-tool aggregates. Missing measurements reduce explicit coverage rather than
becoming fabricated zeros. A summary command exits zero only for `ready` input.

Drift comparison requires an exact compatibility key consisting of report schema,
dataset kind, fingerprints of dataset identity and source hashes, backend,
execution mode, fingerprints of model and prompt identity, and timing mode.
Unbounded provenance labels are never copied into public output. Application
version is fingerprinted and reported separately but intentionally excluded so
otherwise compatible releases can be compared. Mixed or unequal keys produce
`incompatible` without drift calculations.

Numeric per-run distributions use the two-sample Kolmogorov-Smirnov distance;
categorical distributions use total-variation distance. Every assessed metric
needs at least 20 observations in both cohorts. A distance greater than or equal
to the default 0.20 threshold is `detected`; lower distances are `stable`, and
sparse metrics are `insufficient`. A stable top-level result may therefore retain
individually insufficient optional metrics. Comparison normally reports any
status with exit code zero; `--require-assessment` returns nonzero unless the
top-level result is `stable`.

## Interpretation limits

Neither audit emits household IDs, run IDs, provider-call IDs, raw paths, raw
event details, or model reasoning. Demographics remain outside the detector,
agent, peer construction, verifier, and action policy. A Complete Journey
household is not necessarily one person, demographic coverage is incomplete,
and the observational retailer sample is not assumed to be representative.
Nested pipeline stages are not independent populations, and descriptive gaps do
not establish discrimination, statistical significance, or causality.

Operational traces do not currently provide provider-total token usage, hidden
usage, cost, queue age, bytes scanned, reviewer time, detector version, or action-
catalog version. The distance threshold is a review heuristic, not a production
service-level objective.

See [data semantics](data-semantics.md), [reliability](reliability.md),
[productionization](productionization.md), and the
[population API](population-api.md) for the surrounding boundaries.

## Why these tools are standalone

These audits use additive modules, scripts, tests, and this guide so they preserve
newer agent, CLI, web/API, report, manifest, verifier, artifact, and README work.
They intentionally produce independent JSON instead of changing those protected
surfaces. Integrating either audit into runtime decisions or the dashboard would
require a separate compatibility, privacy, and product review.
