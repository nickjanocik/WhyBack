# WhyBack Investigator

This directory contains the internal, localhost-only review interface for
WhyBack. The Node bridge reads the versioned `report.json` and append-only
`trace.jsonl` artifacts produced by Python, validates their paths, sanitizes the
audit details, and serves typed JSON to React. Neither layer calculates
evidence, authors recommendations, or executes customer actions.

## Useful features

- Start a unique new `whyback demo` CLI run with a bounded household count. It
  reuses the currently validated official data, preserves earlier runs for
  audit, and has no scripted or fixture fallback.
- Browse preserved, verifier-sealed CLI runs and search their ranked household
  queues. Bundled examples and unverified output are excluded.
- Compare baseline and recent retailer sales value, basket count, and active
  weeks, with the underlying weekly series.
- Review supported findings, counterevidence, confidence adjustments,
  population context, analytical warnings, and interpretation limits.
- Follow citations into a searchable evidence ledger and filter records by
  evidence role, source tool, or investigation step.
- Follow the exact launched command and sanitized audit activity while the CLI
  runs, then review durable per-household traces, provenance, and report files.
- Use the interface with a keyboard, reduced-motion preferences, or a narrow
  viewport.

## Run in development

Python 3.12 with `uv` and Node.js are required. CI uses Node 24; the current
Vite toolchain supports Node `^20.19.0` or `>=22.12.0`. From the repository
root, prepare the locked Python and web environments:

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

## Live Gemini batch and audited activity

The web launcher is Gemini-only. It executes a fixed command through an
argument array, never a shell string or a browser-selected backend:

```bash
uv run whyback demo --customers <3-24> --backend gemini \
  --output-dir artifacts/local/live-runs/live-<job-id>
```

The supported range is inclusive from three through 24 households. The launch
control defaults to five, so both the 3–4-customer exercise and the committed
five-result deliverable remain reproducible. Every household
can make up to seven real model decisions, so larger batches take longer and can
consume more provider quota.

Before startup, put a rotated credential in the ignored repository-root `.env`
or export it in the server environment:

```dotenv
GEMINI_API_KEY=your-rotated-key
RETENTION_MODEL=gemini-3.7-flash
RETENTION_THINKING_LEVEL=medium
```

`npm run dev`, `npm run server`, and `npm run preview` load that file only into
the local server-side bridge and its Python run process. An exported value takes
precedence. The credential is never sent to React, Vite, an API request or
response, a displayed command, or an audit event. Before enabling the control,
the bridge runs `whyback data validate --official` to verify the prepared-data
identity, schemas, transform version, files, and hashes. If either boundary is
unavailable, the run endpoint fails closed; there is no scripted fallback.
`RETENTION_MODEL` changes the server-selected Gemini model, and
`RETENTION_THINKING_LEVEL` accepts `low`, `medium`, or `high`; neither can be
selected by browser input.

The bridge exposes three read-only artifact endpoints:

- `GET /api/workspace` returns only verifier-sealed live CLI collections, their
  report summaries, live-run readiness, and any collection warnings.
- `GET /api/investigation?collection=<id>&household=<id>` returns one report and
  its sanitized replay trace after validating both identifiers.
- `GET /api/artifact?collection=<id>&household=<id>&file=<name>` streams only an
  allow-listed rendered report or trace.

The run API is asynchronous:

- `POST /api/demo` checks server-side Gemini readiness, validates the requested
  customer count, starts the serialized local job, and returns HTTP `202` with
  a job ID.
- `GET /api/demo/status?job=<job-id>&after=<cursor>` returns the current job
  state and only the audited events recorded after the supplied cursor. The
  browser polls this endpoint while the job is running.
- The live-activity drawer shows the exact fixed CLI command, labels events by
  household, and shows investigation
  questions, selected tools, public decision summaries, tool status, retries,
  verification, and the terminal run state. Evidence-write events are hidden by
  default and appear only when the reviewer enables the **Evidence writes**
  switch.
- The event buffer retains up to 5,000 sanitized audit events. The response
  reports if older events were dropped, and the completed investigation remains
  available in the normal audit view.

Live activity is an external decision and execution record, not model
chain-of-thought. Private chain-of-thought is neither requested nor stored, and
the application rejects hidden-reasoning fields at the audit boundary. The
interface renders only sanitized, allowlisted event details; it does not expose
raw process output.

## Operational boundaries

- Every live job gets a preserved, Git-ignored collection below
  `artifacts/local/live-runs/live-<job-id>/`; a later job never overwrites its
  reports or trace. A terminal collection becomes browseable only after the
  deterministic artifact verifier succeeds and the bridge writes a
  manifest-bound verification seal, even when the CLI exits nonzero after
  recording honest failed household outcomes.
- The bridge binds to `127.0.0.1`, accepts no browser-supplied paths, has a
  bounded process deadline, and permits only one live Gemini batch at a time.
  The default deadline is four hours; `WHYBACK_LIVE_TIMEOUT_MS` can set a value
  from one minute through six hours. Stopping the bridge terminates and waits for
  any active live process before it exits.
- `WHYBACK_DASHBOARD_PORT` changes the built bridge's default `4173` listener.
  The development Vite proxy targets `4173`, so keep that default for
  `npm run dev` unless the proxy configuration is changed too.
- There is no endpoint for data download/preparation, outreach, CRM mutation,
  or action execution. Recommended actions always remain subject to human
  review.

## Frontend quality checks

```bash
cd web
npm run check
```

This runs ESLint, Vitest and Node contract tests, strict TypeScript compilation,
and the production Vite build.
