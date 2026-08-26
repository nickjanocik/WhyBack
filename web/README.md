# WhyBack Investigator

This directory contains the internal, localhost-only review interface for
WhyBack. The React app reads the versioned `report.json` and append-only
`trace.jsonl` artifacts produced by the Python system. It does not calculate
evidence, author recommendations, or execute customer actions.

## Useful features

- Browse artifact collections and search the ranked household investigation
  queue.
- Compare baseline and recent retailer sales value, basket count, and active
  weeks, with the underlying weekly series.
- Review supported findings, counterevidence, confidence adjustments,
  population context, analytical warnings, and interpretation limits.
- Follow citations into a searchable evidence ledger and filter records by
  evidence role, source tool, or investigation step.
- Review the sanitized run timeline, provenance, and deterministic report
  artifacts.
- Run a bounded scripted batch through the local CLI and monitor its audited
  activity while it is running.
- Use the interface with a keyboard, reduced-motion preferences, or a narrow
  viewport.

## Run in development

From the repository root, prepare the Python environment first:

```bash
uv sync --frozen --extra dev
cd web
npm ci
npm run dev
```

Open <http://127.0.0.1:5163>. The development runner starts both Vite and the
artifact bridge. Stop both with `Ctrl-C`.

## Run the production build locally

```bash
cd web
npm ci
npm run build
npm run server
```

Open <http://127.0.0.1:4173>.

## Scripted batch and live audited activity

**Run scripted batch** executes this fixed command through an argument array,
not a shell string:

```bash
uv run whyback demo --customers <5-24> --backend scripted \
  --output-dir artifacts/local/dashboard
```

The range is inclusive: five is the minimum batch and 24 is the full current
synthetic household population.

The run API is asynchronous:

- `POST /api/demo` validates the requested customer count, starts the serialized
  local job, and returns HTTP `202` with a job ID.
- `GET /api/demo/status?job=<job-id>&after=<cursor>` returns the current job
  state and only the audited events recorded after the supplied cursor. The
  browser polls this endpoint while the job is running.
- The live-activity drawer labels events by household and shows investigation
  questions, selected tools, public decision summaries, tool status, evidence
  writes, retries, verification, and the terminal run state.
- The event buffer retains up to 5,000 sanitized audit events. The response
  reports if older events were dropped, and the completed investigation remains
  available in the normal audit view.

Live activity is an external decision and execution record, not model
chain-of-thought. Private chain-of-thought is neither requested nor stored, and
the application rejects hidden-reasoning fields at the audit boundary. The
interface renders only sanitized, allowlisted event details; it does not expose
raw process output.

## Operational boundaries

- Generated output stays below the Git-ignored
  `artifacts/local/dashboard/` tree.
- The bridge binds to `127.0.0.1`, accepts no browser-supplied paths, has a
  120-second process boundary, and permits only one scripted batch at a time.
- There is no endpoint for data download/preparation, Gemini execution,
  outreach, CRM mutation, or action execution. Recommended actions always
  remain subject to human review.

## Frontend quality checks

```bash
cd web
npm run check
```

This runs ESLint, Vitest and Node contract tests, strict TypeScript compilation,
and the production Vite build.
