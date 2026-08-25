# WhyBack repository guide

## Product identity

- Product and repository: **WhyBack**
- Tagline: **Find the why. Choose the way back.**
- Python distribution/package: `whyback`
- Source root: `src/whyback/`
- CLI: `whyback`
- Investigator name: **WhyBack Investigator**

WhyBack is an evidence-grounded customer retention investigation system. It
detects declining engagement, lets a model choose one analytical question at a
time, computes every metric in deterministic code, and recommends only a
human-reviewed Next Best Action.

## Directory responsibilities

- `src/whyback/data/`: pinned-source acquisition, contracts, preparation,
  manifests, and the DuckDB repository boundary.
- `src/whyback/detection/`: transparent decline scoring and deterministic
  candidate selection.
- `src/whyback/tools/`: six deterministic analytical tools and their Pydantic
  contracts. Tool code owns all calculations.
- `src/whyback/agent/`: provider-neutral model decisions, bounded
  orchestration, evidence ledger, action catalog, and final verification.
- `src/whyback/observability/`: append-only audit events and optional portable
  telemetry.
- `src/whyback/reporting/`: deterministic JSON, Markdown, HTML, and trace
  rendering.
- `evals/`: deterministic behavioral scenarios and aggregate metrics.
- `tests/`: hand-calculated, property, integration, orchestration, and golden
  tests that require neither a model key nor full source data.
- `artifacts/`: small reviewer-facing outputs only; raw/prepared datasets and
  caches never belong in Git.

## Architecture invariants

1. The LLM chooses what to investigate; Python/DuckDB calculates the evidence.
2. Application-owned typed state is authoritative. The model receives compact
   state, not raw data or an unbounded transcript.
3. Exactly one analytical action is allowed per model turn. Runs have strict
   tool, turn, retry, timeout, and duplicate-call bounds.
4. Every customer-behavior quantity resolves from run-owned detector evidence
   or an immutable tool `EvidenceRecord`. Operational attempt, retry, and timing
   facts resolve from typed application history and audit events. No displayed
   quantity comes from model-authored prose.
5. The deterministic verifier decides what can be claimed and which catalog
   action is permitted. It checks ownership, limitations, reconciliation,
   failed-tool provenance, confidence, and forbidden numerical prose.
6. `sales_value` is called **retailer sales value**. Promotion rows mean
   availability for a product/store/week, never household exposure.
7. Missing metadata maps to explicit `UNKNOWN` groups; it is never silently
   dropped. Type A delivered coupon identities remain explicitly unavailable.
8. Behavioral peers are primary. Demographics do not drive recommendations.
9. WhyBack recommends actions for human review and performs no external
   outreach or CRM mutation.

## Reliability and audit rules

- Never swallow exceptions silently. Convert expected failures to typed tool
  statuses and let unexpected failures surface with traceable context.
- Retry only explicitly retryable failures and at most once.
- Failed calls emit no supporting evidence. Valid partial evidence retains its
  limitations through rendering.
- Audit concise external decision records only (`investigation_question`,
  selected action, summary). Never request, log, or render hidden chain of
  thought.
- Never fabricate a source download, model execution, test, evaluation,
  artifact, commit, or push. Record skipped and failed work as such.
- Never store secrets, `.env`, raw R data, prepared Parquet, local DuckDB,
  caches, or bulky generated outputs in Git.

## Development and quality gates

Use the lockfile and project environment:

```bash
uv sync --frozen --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python scripts/run_quality_gate.py
```

Run the smallest relevant test set before each milestone commit and the full
quality gate before finalization. Do not record a check in a commit body unless
it actually succeeded.

## Git workflow

- Work only on `codex/whyback-build` (or another already-approved non-protected
  branch); never commit or push directly to `main`, `master`, `dev`, `prod`, or
  `production`.
- Inspect status, full diff, `git diff --check`, and the staged diff before each
  coherent commit.
- Use plain-English subjects and bodies with `What changed`, `Why`, and
  `Checks` sections.
- Push each milestone without force. Never rewrite pushed history merely for
  polish; add a corrective commit.
- Preserve unrelated user work and never use destructive cleanup commands.

## Definition of done

Done means the deterministic system, tests, evaluations, artifacts, docs, and
CLI agree; the complete quality gate was truly captured; official-data and live
model status are honestly reported; an independent final audit found no
material unresolved issue; the working tree is clean; and every possible local
commit is pushed to the working branch.
