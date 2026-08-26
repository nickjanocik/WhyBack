# WhyBack whole-repository cheat sheet

> The plain-English, start-to-finish version. Use this when you need to remember
> what happens, where it happens, and what WhyBack is allowed to claim.

## The 30-second explanation

- **WhyBack looks for customers whose recorded shopping has dropped.** It compares
  an earlier eight-week period with the latest eight-week period
  ([`decline.py` lines 30–64](../src/whyback/detection/decline.py#L30-L64)).
- **The score is a warning light, not a prediction.** It is a hand-written blend
  of the fall in retailer sales value, trips, and active weeks. It is not a
  churn probability ([`decline.py` lines 111–137](../src/whyback/detection/decline.py#L111-L137)).
- **A language model decides which approved question to ask next.** It never
  receives raw tables or writes SQL
  ([`state.py` lines 303–351](../src/whyback/agent/state.py#L303-L351),
  [`gemini_backend.py` lines 281–313](../src/whyback/agent/gemini_backend.py#L281-L313)).
- **Ordinary code owns the quantities.** The detector calculates the warning-light
  score, six fixed tools calculate all post-detection customer-behavior evidence,
  and typed history/audit records operational counts and timing. The model
  calculates none of them
  ([`decline.py` lines 119–269](../src/whyback/detection/decline.py#L119-L269),
  [`registry.py` lines 57–193](../src/whyback/tools/registry.py#L57-L193)).
- **Each answer gets a receipt.** The receipt says which customer, run, tool,
  source, field, limitations, and claim strength produced it
  ([`contracts.py` lines 115–173](../src/whyback/tools/contracts.py#L115-L173)).
- **The model eventually proposes an explanation and one approved action.** It
  must cite those receipts ([`state.py` lines 119–250](../src/whyback/agent/state.py#L119-L250)).
- **A code-based verifier has the final say.** It rejects unsupported evidence,
  causal language, ignored counterevidence, bad confidence, and actions whose
  prerequisites are not met ([`verifier.py` lines 915–1434](../src/whyback/agent/verifier.py#L915-L1434)).
- **A human gets reports and makes the real decision.** WhyBack does not contact
  a customer, issue an offer, or change a CRM
  ([`AGENTS.md` lines 53–57](../AGENTS.md#L53-L57)).

## Remember this sentence

> **The model chooses the next question; deterministic code calculates the
> evidence; deterministic code also decides what may be published.**

That separation is the heart of the repository
([`README.md` lines 5–12](../README.md#L5-L12)).

---

## The repository as a set of drawers

- [`src/whyback/data/`](../src/whyback/data/) — gets, checks, converts, hashes,
  and opens the data.
- [`src/whyback/detection/`](../src/whyback/detection/) — finds customers with a
  large decline.
- [`src/whyback/tools/`](../src/whyback/tools/) — the six calculators that own
  post-detection customer-behavior evidence.
- [`src/whyback/agent/`](../src/whyback/agent/) — the model adapter, bounded loop,
  case state, evidence ledger, action catalog, and final verifier.
- [`src/whyback/observability/`](../src/whyback/observability/) — the sanitized,
  append-only audit diary.
- [`src/whyback/reporting/`](../src/whyback/reporting/) — turns verified state into
  JSON, Markdown, HTML, and a trace viewer.
- [`src/whyback/cli.py`](../src/whyback/cli.py) — all terminal commands.
- [`web/server/`](../web/server/) — localhost-only bridge that safely reads
  artifacts and can launch one bounded Gemini batch.
- [`web/src/`](../web/src/) — React reviewer screen. It displays results; it
  does not calculate evidence.
- [`configs/`](../configs/) — human-readable application settings and the six
  approved recommendations.
- [`tests/`](../tests/) and [`evals/`](../evals/) — executable proof that the
  calculations, limits, failure behavior, and report claims work as intended.
- [`scripts/`](../scripts/) — demo building, artifact verification, and the full
  quality gate.
- [`artifacts/`](../artifacts/) — small, reviewer-facing outputs. Raw data,
  prepared Parquet, secrets, and local live runs do not belong in Git.

---

## Before running anything

- You need Python 3.12 and `uv`; the Python range is declared in
  [`pyproject.toml` lines 5–27](../pyproject.toml#L5-L27).
- The web app also needs Node/npm; its commands and packages are in
  [`web/package.json` lines 1–40](../web/package.json#L1-L40).
- From the repository root, install the locked Python environment:

```bash
uv sync --frozen --extra dev
```

- Install the web packages only when you need the browser interface:

```bash
cd web
npm ci
cd ..
```

- See every Python command:

```bash
uv run whyback --help
```

- The word `whyback` reaches the Typer app in `whyback.cli:app` because of the
  executable entry in [`pyproject.toml` lines 38–39](../pyproject.toml#L38-L39).

---

## Pick the journey you actually mean

### Journey A — quickest safe demonstration, no API key or official data

```bash
uv run whyback demo --customers 5 --output-dir artifacts/local/dashboard
```

- This is the default `scripted` backend
  ([`cli.py` lines 323–372](../src/whyback/cli.py#L323-L372)).
- It creates a small synthetic grocery-like dataset, then exercises the real
  detector, tools, evidence ledger, runner, verifier, reports, trace, and
  manifest ([`demo.py` lines 718–898](../src/whyback/demo.py#L718-L898)).
- “Scripted” means the sequence of model decisions is predetermined. The
  calculated evidence is still real code output; it is not a claim that a live
  model ran ([`scripted_backend.py` lines 36–85](../src/whyback/agent/scripted_backend.py#L36-L85)).
- This command writes to the dashboard's ignored **Generated runs** collection,
  `artifacts/local/dashboard/`. Omitting
  `--output-dir` intentionally rebuilds the committed `artifacts/demo/` fixture.
- Verify it without changing it:

```bash
uv run whyback verify-artifacts artifacts/local/dashboard
```

### Journey B — official data from the terminal

```bash
uv run whyback data prepare --full
uv run whyback data validate --official
uv run whyback detect --top 20 --output-dir artifacts/local/detection
uv run whyback investigate --household-id 5 --backend scripted
```

- `data prepare --full` downloads missing pinned source files by default,
  verifies them, converts them, and writes a manifest
  ([`cli.py` lines 122–165](../src/whyback/cli.py#L122-L165)).
- `data validate --official` rechecks the strict manifest structure, source and
  transformation identity, prepared-table declarations, and file hashes before
  analysis. It does not re-profile every Parquet column independently
  ([`cli.py` lines 72–104](../src/whyback/cli.py#L72-L104)).
- `detect` ranks eligible households by the transparent decline score
  ([`cli.py` lines 168–244](../src/whyback/cli.py#L168-L244)).
- `investigate` runs one household through the full agent/report pipeline
  ([`cli.py` lines 247–320](../src/whyback/cli.py#L247-L320)).
- Change `--backend scripted` to `--backend gemini` only when you intentionally
  want to send compact case state to Gemini and have a server-side key.

### Journey C — browser reviewer app and optional live Gemini batch

Development mode:

```bash
cd web
npm run dev
```

- Open <http://127.0.0.1:5163>.
- One command starts two local programs: the Node artifact bridge on port 4173
  and Vite on port 5163
  ([`dev.mjs` lines 12–45](../web/scripts/dev.mjs#L12-L45)).
- The app can browse existing artifacts without a model key.
- A live browser-launched run additionally needs:
  - prepared **official** data that passes `whyback data validate --official`;
  - `GEMINI_API_KEY` exported in the server environment or placed in the
    ignored repository-root `.env`;
  - a requested batch size from 3 through 24; five is the default.
- The key stays on the server. The development launcher explicitly removes it
  from Vite's environment ([`dev.mjs` lines 42–45](../web/scripts/dev.mjs#L42-L45)).
- The browser may only launch this fixed shape of command:

```text
uv run whyback demo --customers N --backend gemini \
  --output-dir artifacts/local/live-runs/live-<job-id>
```

- The Node bridge passes an argument array with `shell: false`; the browser
  cannot supply a path, backend name, shell fragment, or arbitrary command
  ([`index.mjs` lines 194–206](../web/server/index.mjs#L194-L206),
  [`index.mjs` lines 392–477](../web/server/index.mjs#L392-L477)).
- A completed live collection is browseable only after the deterministic
  artifact verifier succeeds and a seal binds the manifest and artifact-tree
  hashes ([`live-runs.mjs` lines 192–339](../web/server/live-runs.mjs#L192-L339)).

Production-style local build:

```bash
cd web
npm run build
npm run server
```

- Open <http://127.0.0.1:4173>.
- This is still a localhost review tool, not a hosted customer-facing product
  ([`web/README.md` lines 1–5](../web/README.md#L1-L5)).

---

## The full Python sequence, one step at a time

### 1. The command is routed

- The `whyback` executable enters the Typer application in
  [`cli.py` lines 22–45](../src/whyback/cli.py#L22-L45).
- The selected command loads non-secret settings from `configs/app.toml`
  ([`config.py` lines 77–101](../src/whyback/config.py#L77-L101),
  [`app.toml` lines 1–25](../configs/app.toml#L1-L25)).
- Environment variables can choose the model and thinking level; credentials
  are not stored in that settings object.

### 2. Raw source files become trusted analytical tables

- The official source is pinned to one repository commit and eight exact files.
  Each expected file has a size and SHA-256 digest
  ([`download.py` lines 21–110](../src/whyback/data/download.py#L21-L110)).
- The downloader refuses the wrong file instead of quietly accepting it
  ([`download.py` lines 88–159](../src/whyback/data/download.py#L88-L159)).
- Preparation reads `.rda`/`.rds` files and writes Parquet. Think of Parquet as
  a compact, column-oriented filing format that Python and analytics engines
  can scan efficiently ([`prepare.py` lines 74–351](../src/whyback/data/prepare.py#L74-L351)).
- Preparation standardizes names/types and produces ten tables: transactions,
  products, demographics, campaigns, campaign descriptions, coupons, coupon
  redemptions, promotion state, household-week summaries, and basket summaries
  ([`prepare.py` lines 30–71](../src/whyback/data/prepare.py#L30-L71),
  [`contracts.py` lines 26–94](../src/whyback/data/contracts.py#L26-L94)).
- A manifest is a tamper-evident packing slip. It records input/output hashes,
  row counts, schemas, missingness, source identity, and transformation version
  ([`manifest.py` lines 38–127](../src/whyback/data/manifest.py#L38-L127)).

### 3. DuckDB opens the prepared files read-only

- `DataRepository` requires each requested file, validates the strict manifest,
  source/transform identity, table declarations, and SHA-256 hashes, then
  creates read-only-style DuckDB views over the Parquet files. It trusts the
  manifest's recorded schema rather than re-profiling every column here
  ([`repository.py` lines 46–168](../src/whyback/data/repository.py#L46-L168)).
- DuckDB is like SQLite for analytical questions: it runs inside the process,
  but is designed to scan and aggregate columns efficiently. WhyBack does not
  first load millions of rows into a remote database server.
- The repository permits bound parameters and controlled query code. The model
  never supplies SQL ([`repository.py` lines 164–209](../src/whyback/data/repository.py#L164-L209)).

### 4. The detector finds decline candidates

- The last available week anchors two adjacent windows: older “baseline” and
  newer “recent” ([`decline.py` lines 30–64](../src/whyback/detection/decline.py#L30-L64)).
- A household must have enough baseline activity to be eligible. Current
  defaults are at least four active weeks, at least six baskets, and positive
  baseline retailer sales value
  ([`app.toml` lines 12–17](../configs/app.toml#L12-L17)).
- Each drop is clipped between zero and one. Growth does not create a negative
  decline score:

```text
sales drop       = (baseline sales - recent sales) / baseline sales
trip drop        = (baseline trips - recent trips) / baseline trips
active-week drop = (baseline active weeks - recent active weeks) / baseline active weeks

decline score = 50% sales drop + 30% trip drop + 20% active-week drop
```

- The current flag threshold is `0.30`; the score calculation and candidate
  selection are separate, deterministic steps
  ([`decline.py` lines 111–137](../src/whyback/detection/decline.py#L111-L137),
  [`decline.py` lines 196–269](../src/whyback/detection/decline.py#L196-L269)).
- The detector returns a typed snapshot, not a diagnosis. “High score” means
  “worth investigating,” not “this customer churned.”

### 5. One customer becomes one controlled case file

- `locate_snapshot()` obtains the requested eligible household's detector facts
  ([`demo.py` lines 1210–1232](../src/whyback/demo.py#L1210-L1232)).
- `run_investigation()` connects the repository, backend, tool registry, action
  catalog, audit writer, runner, verifier, and renderers
  ([`demo.py` lines 398–526](../src/whyback/demo.py#L398-L526)).
- `InvestigationState.start()` creates an immutable case file containing the
  household, windows, detector snapshot, empty history/ledger, and budgets
  ([`state.py` lines 253–300](../src/whyback/agent/state.py#L253-L300)).

### 6. The model sees a small menu and compact case summary

- The case summary includes detector facts, completed-tool summaries, evidence
  IDs/values, limitations, open questions, and remaining budgets—not raw rows
  or an unlimited chat transcript
  ([`state.py` lines 303–351](../src/whyback/agent/state.py#L303-L351)).
- The available menu contains the registered tools that have not been marked
  unavailable, plus `finish_investigation`. A tool may appear again with
  different valid arguments; only the exact same normalized call is refused.
  During a repair turn or after the tool budget is exhausted, finishing is the
  only option
  ([`runner.py` lines 229–238](../src/whyback/agent/runner.py#L229-L238),
  [`runner.py` lines 464–537](../src/whyback/agent/runner.py#L464-L537)).
- The Gemini adapter forces function calling and rejects zero, multiple, or
  unknown calls ([`gemini_backend.py` lines 240–414](../src/whyback/agent/gemini_backend.py#L240-L414)).
- The default ceilings are five actual tool attempts, six model decisions, one
  retry for an explicitly retryable failure, and a 30-second tool timeout
  ([`app.toml` lines 19–25](../configs/app.toml#L19-L25)).

### 7. One deterministic tool answers one question

- The registry maps the chosen name to a strict input form and one Python
  handler ([`registry.py` lines 57–193](../src/whyback/tools/registry.py#L57-L193)).
- The runner rejects the wrong household, invalid arguments, and exact duplicate
  normalized calls before calculation. Unavailable tools are removed from the
  offered menu; if Gemini nevertheless asks for a function it was not offered,
  the Gemini adapter rejects that response
  ([`runner.py` lines 464–637](../src/whyback/agent/runner.py#L464-L637),
  [`gemini_backend.py` lines 421–439](../src/whyback/agent/gemini_backend.py#L421-L439)).
- The runner executes the tool behind a timeout boundary. An expected problem
  becomes a typed status; an unexpected integrity problem remains traceable
  ([`runner.py` lines 729–798](../src/whyback/agent/runner.py#L729-L798)).

The six questions are:

- **Customer Trend:** Did value, number of visits, active weeks, basket value,
  item quantity, product variety, recency, or the weekly direction change?
  ([`trend.py` lines 214–543](../src/whyback/tools/trend.py#L214-L543))
- **Category Decomposition:** Which product categories account for the recorded
  loss or gain, and are target-excluded customers moving similarly?
  ([`category.py` lines 297–831](../src/whyback/tools/category.py#L297-L831))
- **Basket Behavior:** Were there fewer baskets, smaller baskets, different
  contents, a longer gap between visits, or a store change?
  ([`basket.py` lines 248–558](../src/whyback/tools/basket.py#L248-L558))
- **Promotion Response:** Did purchases associated with a recorded product/store/
  week promotion availability change? Availability does **not** prove the
  household saw the offer
  ([`promotion.py` lines 59–335](../src/whyback/tools/promotion.py#L59-L335)).
- **Coupon/Campaign History:** Which campaigns, redemptions, coupon baskets, and
  discounts are recorded? Some Type A delivered-coupon identities are genuinely
  absent and stay marked `partial`
  ([`coupon.py` lines 32–261](../src/whyback/tools/coupon.py#L32-L261)).
- **Peer Comparison:** Is the target's change unusual compared with all eligible
  households and behaviorally similar shoppers? The target is excluded and
  demographics do not drive the match
  ([`peer.py` lines 118–623](../src/whyback/tools/peer.py#L118-L623)).

### 8. The answer is stored as evidence, not prose

- A successful or valid partial result can produce immutable
  `EvidenceRecord`s. Each has a unique ID such as `ev_<call>_001`
  ([`common.py` lines 85–130](../src/whyback/tools/common.py#L85-L130)).
- `ok` means complete; `partial` means useful but limited. `missing_data`,
  `invalid_request`, `retryable_error`, and `fatal_error` produce no supporting
  evidence ([`contracts.py` lines 200–237](../src/whyback/tools/contracts.py#L200-L237)).
- The common result contract checks that every receipt names the result's tool
  and call. `EvidenceLedger.add_tool_result()` then independently checks success,
  run, household, call ownership, and unique IDs
  ([`contracts.py` lines 217–237](../src/whyback/tools/contracts.py#L217-L237),
  [`evidence.py` lines 39–72](../src/whyback/agent/evidence.py#L39-L72)).
- The typed history also records failed attempts, retries, elapsed time, and safe
  decision summaries. A failure remains visible but cannot support a claim.

### 9. The loop continues or the model proposes a finish

- After each answer, the next model decision gets the newly updated compact
  state. This is “dynamic orchestration”: the next question can depend on the
  actual previous answer.
- A finish proposal must name one catalog action, propose a confidence level,
  describe up to four qualitative drivers, cite exact support and
  counterevidence IDs, disclose limitations, and account for the evidence set
  ([`state.py` lines 119–250](../src/whyback/agent/state.py#L119-L250)).
- Free-form prose is intentionally restricted. Numbers must come from evidence
  fields, and causal statements are not publishable.

### 10. The deterministic verifier decides what survives

- It checks that every cited ID exists, belongs to this run/customer, and came
  from a successful tool—not a failed attempt
  ([`verifier.py` lines 923–1120](../src/whyback/agent/verifier.py#L923-L1120)).
- It checks category totals reconcile, promotion joins did not multiply sales,
  and comparison populations excluded the target
  ([`verifier.py` lines 1392–1434](../src/whyback/agent/verifier.py#L1392-L1434)).
- It finds required broad/mixed counterevidence and rejects a proposal that
  ignores it ([`verifier.py` lines 398–525](../src/whyback/agent/verifier.py#L398-L525)).
- It checks action prerequisites and contraindications against the ledger, then
  may lower confidence according to code-owned rules
  ([`verifier.py` lines 552–838](../src/whyback/agent/verifier.py#L552-L838)).
- It replaces model-authored final wording with safe code/catalog wording where
  appropriate ([`verifier.py` lines 841–912](../src/whyback/agent/verifier.py#L841-L912)).
- A rejected finish gets at most one structured repair opportunity. If a safe
  conclusion still cannot be produced, the runner publishes
  `INSUFFICIENT_EVIDENCE` or fails closed rather than guessing
  ([`runner.py` lines 801–934](../src/whyback/agent/runner.py#L801-L934)).

### 11. Only one of six catalog outcomes can be recommended

- `CATEGORY_WINBACK` — a specific category loss has enough support.
- `VISIT_FREQUENCY_REACTIVATION` — the evidence supports a frequency-led drop.
- `PROMOTION_VALUE_REENGAGEMENT` — qualifying promotion-availability or recorded
  coupon-history evidence supports it.
- `PERSONALIZED_CHECK_IN` — a broader supported decline fits the prerequisites.
- `MONITOR` — evidence supports watching rather than intervening.
- `INSUFFICIENT_EVIDENCE` — the no-action fallback. A model can propose it, but
  the verifier normally accepts it only when no supported catalog action fits;
  the runner can also construct it for the separately verified safe fallback.

The exact rules, contraindications, human-review flag, success metrics, and
holdout measurement plans live in
[`configs/actions.yaml`](../configs/actions.yaml). The catalog loader fails
closed if the allowlist or structure is wrong
([`actions.py` lines 186–275](../src/whyback/agent/actions.py#L186-L275)).

### 12. The run becomes replayable files

- `build_report_data()` constructs one internally cross-checked report object
  from the
  terminal state, verifier decision, ledger, tool history, and provenance
  ([`render.py` lines 503–725](../src/whyback/reporting/render.py#L503-L725)).
- `write_report_bundle()` writes:

  - `report.json` — machine-readable source for the browser;
  - `report.md` — readable text;
  - `report.html` — standalone human report.

  Those three outputs are built at
  [`render.py` lines 793–840](../src/whyback/reporting/render.py#L793-L840).
- `trace.jsonl` is written as the run happens. Each line is one sanitized,
  ordered audit event ([`audit.py` lines 20–107](../src/whyback/observability/audit.py#L20-L107)).
- The trace records public questions, selected functions, statuses, safe
  summaries, evidence IDs, and verification results. It does not request or
  store hidden model reasoning or chain-of-thought
  ([`prompts.py` lines 9–22](../src/whyback/agent/prompts.py#L9-L22),
  [`AGENTS.md` lines 66–68](../AGENTS.md#L66-L68)).
- `write_trace_html()` separately turns that JSONL diary into the readable,
  standalone `trace.html`
  ([`trace.py` lines 198–225](../src/whyback/reporting/trace.py#L198-L225)).
- Batch/demo output also gets a selected-order results index and a manifest with
  hashes so later review can detect missing or changed files
  ([`demo.py` lines 625–715](../src/whyback/demo.py#L625-L715)).

---

## What the browser does, from `npm run dev` to the screen

### Startup

- `npm run dev` calls [`web/scripts/dev.mjs`](../web/scripts/dev.mjs).
- The script starts the Node bridge and Vite together and shuts both down if one
  exits ([`dev.mjs` lines 12–45](../web/scripts/dev.mjs#L12-L45)).
- The server startup file optionally reads the ignored root `.env`, preserving
  an explicitly exported Gemini key
  ([`start.mjs` lines 9–43](../web/server/start.mjs#L9-L43)).
- The bridge binds to loopback, applies security headers, and rejects unwanted
  hosts/mutations ([`index.mjs` lines 51–110](../web/server/index.mjs#L51-L110),
  [`index.mjs` lines 715–841](../web/server/index.mjs#L715-L841)).

### Loading existing results

- React asks `GET /api/workspace` for safe collection summaries
  ([`App.tsx` lines 95–127](../web/src/App.tsx#L95-L127)).
- The bridge discovers only named allowlisted static collections and valid
  sealed live collections. Unvalidated browser text never becomes a filesystem
  path; only allowlisted collection/file names and validated household IDs do
  ([`artifacts.mjs` lines 13–87](../web/server/artifacts.mjs#L13-L87),
  [`artifacts.mjs` lines 245–296](../web/server/artifacts.mjs#L245-L296)).
- React chooses a collection/household and asks
  `GET /api/investigation?collection=...&household=...`
  ([`App.tsx` lines 246–262](../web/src/App.tsx#L246-L262)).
- The bridge reads `report.json`, safely normalizes allowlisted trace details,
  and returns the display package
  ([`artifacts.mjs` lines 294–387](../web/server/artifacts.mjs#L294-L387)).

### What appears

- `CandidateRail` — choose an artifact collection and ranked household
  ([`CandidateRail.tsx` lines 18–142](../web/src/components/CandidateRail.tsx#L18-L142)).
- `OverviewPanel` — decline metrics, chart, supported finding, recommendation,
  confidence, measurement plan, and population context
  ([`OverviewPanel.tsx` lines 36–419](../web/src/components/OverviewPanel.tsx#L36-L419)).
- `EvidencePanel` — search/filter the receipts and follow citations
  ([`EvidencePanel.tsx` lines 34–225](../web/src/components/EvidencePanel.tsx#L34-L225)).
- `AuditPanel` — provenance, investigation path, warnings, saved trace, and
  downloadable report links
  ([`AuditPanel.tsx` lines 28–112](../web/src/components/AuditPanel.tsx#L28-L112)).
- `RunDemoDialog` — confirm a bounded 3–24-household live batch
  ([`RunDemoDialog.tsx` lines 22–184](../web/src/components/RunDemoDialog.tsx#L22-L184)).
- `LiveTraceDrawer` — see sanitized progress while the local job runs
  ([`LiveTraceDrawer.tsx` lines 29–296](../web/src/components/LiveTraceDrawer.tsx#L29-L296)).

### Launching and following a live batch

- `POST /api/demo` accepts only a JSON object with a valid customer count and
  returns a job ID with HTTP 202
  ([`index.mjs` lines 679–705](../web/server/index.mjs#L679-L705)).
- The server serializes jobs: one live Gemini batch at a time
  ([`live-trace.mjs` lines 367–560](../web/server/live-trace.mjs#L367-L560)).
- React polls `GET /api/demo/status?job=...&after=...` and asks only for new
  events after its cursor ([`App.tsx` lines 129–244](../web/src/App.tsx#L129-L244)).
- The activity buffer keeps at most 5,000 sanitized events and explicitly says
  when older ones were dropped.
- On completion, the bridge runs `scripts/verify_artifacts.py`. Only a verified,
  sealed output joins the normal collection list
  ([`index.mjs` lines 508–562](../web/server/index.mjs#L508-L562)).
- There is **no** endpoint for downloading/preparing data, sending messages,
  issuing coupons, changing a CRM, or executing a recommendation.

---

## CLI command crib sheet

- `uv run whyback --version` — print the package version
  ([`cli.py` lines 32–45](../src/whyback/cli.py#L32-L45)).
- `uv run whyback config` — show effective non-secret settings
  ([`cli.py` lines 50–55](../src/whyback/cli.py#L50-L55)).
- `uv run whyback data status` — show pinned source and whether a prepared
  manifest file exists. This is an existence check, not validation
  ([`cli.py` lines 58–69](../src/whyback/cli.py#L58-L69)).
- `uv run whyback data download` — fetch and verify the eight official source
  files ([`cli.py` lines 107–119](../src/whyback/cli.py#L107-L119)).
- `uv run whyback data prepare --full` — make all validated analytical tables
  ([`cli.py` lines 122–165](../src/whyback/cli.py#L122-L165)).
- `uv run whyback data validate --official` — prove the manifest claims the
  exact pinned official identity and the requested prepared files still match
  their declared hashes ([`cli.py` lines 72–104](../src/whyback/cli.py#L72-L104)).
- `uv run whyback detect --top 20` — rank decline candidates
  ([`cli.py` lines 168–244](../src/whyback/cli.py#L168-L244)).
- `uv run whyback investigate --household-id ID` — investigate one eligible
  household; scripted by default ([`cli.py` lines 247–320](../src/whyback/cli.py#L247-L320)).
- `uv run whyback demo --customers 5` — rebuild the credential-free synthetic
  reviewer bundle ([`cli.py` lines 323–372](../src/whyback/cli.py#L323-L372)).
- `uv run whyback demo --customers 5 --backend gemini` — official-data Gemini
  batch. With a key it attempts live investigations; without a key it writes an
  honest `skipped_no_api_key` bundle and makes no model call
  ([`demo.py` lines 941–967](../src/whyback/demo.py#L941-L967)).
- `uv run whyback verify-artifacts PATH` — read-only verification of hashes,
  grounding, trace order, and execution labels
  ([`cli.py` lines 375–411](../src/whyback/cli.py#L375-L411)).
- `uv run whyback official-type-a` — official-data scripted control showing the
  genuine Type A coupon limitation
  ([`cli.py` lines 414–436](../src/whyback/cli.py#L414-L436)).

---

## Output-file crib sheet

- `manifest.json` — the artifact tree or standalone run's identity card and hash
  inventory.
- `.whyback-owned-artifact-root.json` — batch/demo marker telling the publisher
  this generated tree is safe to replace. A standalone investigation does not
  receive this marker.
- `results.json` / `RESULTS.md` — selected-order batch reports and a readable
  household/action summary.
- `decline_candidates.csv` / `sensitivity.csv` — detector ranking and fixed
  threshold-count diagnostics.
- `data_provenance.json` — official-data identity snapshot for an official batch
  or standalone investigation.
- `live_model_status.json` — honest `skipped_no_api_key` status when an official
  Gemini batch was requested without a key.
- `failure_example/`, `type_a_partial_example/`, and
  `evals/normalized_runs.json` — synthetic-demo controls for persistent failure,
  partial coupon evidence, and deterministic evaluation input.
- `customer_<id>/report.json` — authoritative machine-readable investigation.
- `customer_<id>/report.md` — plain report.
- `customer_<id>/report.html` — styled standalone report.
- `customer_<id>/trace.jsonl` — append-only audit diary.
- `customer_<id>/trace.html` — readable audit replay.
- `artifacts/tests/test_audit.json` — authoritative captured quality-gate
  transcript; its Markdown companion is `TEST_AUDIT.md`.
- `artifacts/local/` — local/large/live outputs that should stay out of Git.

Use this to validate a bundle:

```bash
uv run whyback verify-artifacts artifacts/demo
```

The verifier is deliberately much stricter than “can I open the JSON?” It
recalculates hashes and cross-checks manifests, reports, evidence ownership,
traces, execution labels, and captured quality/evaluation claims
([`verify_artifacts.py` lines 3401–3763](../scripts/verify_artifacts.py#L3401-L3763)).

---

## Safety words that matter

- **Typed:** data must fit a strict named form before the program accepts it.
- **Immutable:** once accepted into the case record, it cannot be silently
  changed in place.
- **Deterministic:** ordinary rules calculate or verify the answer; the model is
  not allowed to invent that result.
- **Bounded:** hard limits cap turns, attempts, retries, time, request size, or
  retained history.
- **Provenance:** the recorded answer to “where did this data, calculation, and
  run come from?”
- **Retailer sales value:** recorded sales at this retailer. Not profit, total
  household spending, or grocery need.
- **Decline Score:** transparent investigation priority. Not a probability.
- **Promotion availability:** the product/store/week record says an offer was
  available there. It does not prove this household saw it.
- **Descriptive:** says what the records show.
- **Associational:** cautiously says two recorded patterns occur together.
- **Causal:** says one thing caused another; current publication rules reject it
  ([`methodology.py` lines 11–16](../src/whyback/methodology.py#L11-L16)).
- **Counterevidence:** relevant facts that weaken or broaden the proposed story.
- **Partial:** valid evidence with a required limitation; not a broken feature.
- **Failed:** no supporting evidence was created.
- **Human review:** every recommendation waits for a person.

---

## Common misunderstandings, corrected

- “The AI calculates the metrics.” — **No.** The model chooses a tool; Python/
  DuckDB calculate the metrics.
- “The agent is just the LLM.” — **No.** The model is one replaceable decision
  component. The agent includes bounded orchestration, tools, state, ledger,
  verifier, action catalog, audit, and reports.
- “A score of 0.8 means 80% likely to churn.” — **No.** It is a weighted decline
  indicator from 0 to 1.
- “No recent transactions means the household stopped buying groceries.” —
  **No.** The data cannot see competitors or many real-life circumstances.
- “A promotion row proves exposure.” — **No.** It proves recorded availability
  at a product/store/week combination.
- “Peer comparison proves the cause.” — **No.** It provides descriptive context,
  not a randomized control or complete seasonal adjustment.
- “The app takes action.” — **No.** It displays a proposed, human-reviewed next
  action and a plan for measuring it.
- “The website is the analytics engine.” — **No.** Python produces verified
  artifacts; Node safely reads/launches; React displays.
- “A live run silently falls back to the scripted demo.” — **No.** A missing
  key creates an honest skipped CLI bundle or disables browser launch. Invalid
  official data, a timeout, or failed artifact verification fails the live path;
  none of these conditions substitutes scripted decisions.

---

## Failure behavior in one glance

- Bad arguments or wrong household → `invalid_request`; no evidence.
- Required data absent → `missing_data`; no evidence.
- Temporary/timeout-style issue → `retryable_error`; at most one retry.
- Integrity or nonretryable execution issue → `fatal_error`; no evidence.
- Useful result with an honest caveat → `partial`; evidence plus limitation.
- Exact duplicate tool call → rejected and recorded; the model decision was
  already spent, but no tool attempt runs and no tool-attempt budget is spent
  ([`runner.py` lines 293–298](../src/whyback/agent/runner.py#L293-L298),
  [`runner.py` lines 500–537](../src/whyback/agent/runner.py#L500-L537)).
- Model finish fails verification → at most one repair turn, and only when model
  turn budget remains ([`runner.py` lines 431–462](../src/whyback/agent/runner.py#L431-L462)).
- Repair still fails or evidence is inadequate → safe insufficiency/fail-closed
  result, never an improvised story.
- Web child fails or times out → job failure with sanitized public message; raw
  output is not sent to the browser.
- Live output fails artifact verification → no seal and no browseable collection.

---

## How to check the repository

Complete auditable repository gate:

```bash
uv run python scripts/run_quality_gate.py
```

It installs the locked Python and web dependencies, runs formatting, lint,
strict type checking, Python tests with branch coverage, the web lint/test/build
checks, deterministic evaluations, and artifact verification. Secret and
dependency audits remain separate hosted-CI security jobs
([`run_quality_gate.py`](../scripts/run_quality_gate.py)).

Fast standalone web gate after `npm ci`:

```bash
cd web
npm run check
```

This runs ESLint, React/Node tests, strict TypeScript compilation, and the Vite
production build ([`package.json` lines 6–15](../web/package.json#L6-L15)).

Test/evaluation mental model:

- Unit tests check hand-calculated contracts and calculations.
- Property tests generate many inputs to test mathematical invariants.
- Integration tests follow prepared data through the full pipeline.
- Orchestration tests attack budgets, duplicates, retry, malformed model output,
  repair, and fallback behavior.
- Golden/report tests keep rendered artifacts stable and grounded.
- Deterministic evaluations exercise 12 behavioral stories, including frequency,
  category, promotion, broad decline, insufficient populations, timeouts, and a
  causal-claim attack ([`scenarios.yaml` lines 1–175](../evals/scenarios.yaml#L1-L175)).
- The evaluation scorer is not another AI judge: it does not invoke a model or
  tool. It checks normalized, typed outcomes created by the real scripted
  orchestration path
  ([`run_evals.py` lines 1–6](../evals/run_evals.py#L1-L6),
  [`run_evals.py` lines 876–1014](../evals/run_evals.py#L876-L1014),
  [`evaluation_cases.py` lines 539–574](../src/whyback/evaluation_cases.py#L539-L574)).
- The current test marked `live` skips only when `GEMINI_API_KEY` is absent. If
  it starts and the network/provider fails, the test fails rather than quietly
  skipping. Any skip is recorded; it is not presented as a successful live run
  ([`test_gemini_backend_live.py` lines 43–49](../tests/live/test_gemini_backend_live.py#L43-L49)).

---

## Current wiring details worth remembering

- The live backend implemented now is **Gemini**. Old OpenAI labels may appear
  in preserved historical artifacts; they are provenance, not current wiring.
- Python does not automatically load `.env`. The web bridge startup does. For a
  direct CLI live run, export `GEMINI_API_KEY` in the shell.
- `whyback demo --backend gemini` intentionally uses official prepared data.
  A direct `whyback investigate --backend gemini` can use an explicitly selected
  prepared directory only when its manifest has one of WhyBack's two recognized
  identities: the official source or the synthetic fixture
  ([`demo.py` lines 318–361](../src/whyback/demo.py#L318-L361)).
- `locate_snapshot()` receives configured window lengths but currently uses the
  default detector thresholds. The checked-in `app.toml` values match those
  defaults ([`demo.py` lines 1210–1232](../src/whyback/demo.py#L1210-L1232)).
- `run_investigation()` currently relies on default `AgentConfig` values rather
  than passing `settings.agent`; the checked-in TOML also matches those defaults
  ([`demo.py` lines 398–526](../src/whyback/demo.py#L398-L526)).
- The Vite development proxy is fixed to bridge port 4173. Changing only the
  server's `WHYBACK_DASHBOARD_PORT` will not move that proxy
  ([`vite.config.ts` lines 8–26](../web/vite.config.ts#L8-L26)).
- The live-job registry is in memory. Restarting the bridge forgets job-status
  objects, but already published, sealed artifact directories remain on disk.
- The dashboard's fixed local collection is `artifacts/local/dashboard`.
  A default standalone `whyback investigate` writes to
  `artifacts/local/customer_<id>` and is not automatically listed in the
  browser; browser-launched live runs use sealed directories below
  `artifacts/local/live-runs/`
  ([`artifacts.mjs` lines 13–18](../web/server/artifacts.mjs#L13-L18),
  [`cli.py` lines 284–286](../src/whyback/cli.py#L284-L286)).
- The CLI artifact wrapper deliberately permits an honestly recorded historical
  “live skipped” manifest; direct verifier/quality-gate modes can demand a real
  live result ([`cli.py` lines 392–400](../src/whyback/cli.py#L392-L400)).

---

## “Where do I look?” index

- “What command starts this?” → [`cli.py`](../src/whyback/cli.py) and
  [`web/package.json`](../web/package.json).
- “Where are defaults?” → [`configs/app.toml`](../configs/app.toml) and
  [`config.py`](../src/whyback/config.py).
- “How is raw data trusted?” → [`download.py`](../src/whyback/data/download.py),
  [`prepare.py`](../src/whyback/data/prepare.py), and
  [`repository.py`](../src/whyback/data/repository.py).
- “How is decline calculated?” → [`decline.py`](../src/whyback/detection/decline.py).
- “Which tool name runs which code?” → [`registry.py`](../src/whyback/tools/registry.py).
- “What can the model see?” → `compact_model_context()` in
  [`state.py` lines 303–351](../src/whyback/agent/state.py#L303-L351).
- “Where is the main loop?” → `InvestigationRunner.run()` in
  [`runner.py` lines 181–462](../src/whyback/agent/runner.py#L181-L462).
- “How is Gemini called?” → [`gemini_backend.py`](../src/whyback/agent/gemini_backend.py).
- “Where are evidence receipts stored?” → [`evidence.py`](../src/whyback/agent/evidence.py).
- “Why was a final claim/action rejected?” → [`verifier.py`](../src/whyback/agent/verifier.py)
  and [`configs/actions.yaml`](../configs/actions.yaml).
- “How are reports made?” → [`render.py`](../src/whyback/reporting/render.py) and
  [`models.py`](../src/whyback/reporting/models.py).
- “What did the run do?” → `trace.jsonl` plus
  [`events.py`](../src/whyback/observability/events.py).
- “How does the browser read artifacts?” →
  [`web/server/artifacts.mjs`](../web/server/artifacts.mjs).
- “How does the browser start a live run?” →
  [`web/server/index.mjs`](../web/server/index.mjs),
  [`web/server/live-trace.mjs`](../web/server/live-trace.mjs), and
  [`web/server/live-runs.mjs`](../web/server/live-runs.mjs).
- “What owns the main browser state?” → [`App.tsx`](../web/src/App.tsx).
- “What proves it works?” → [`tests/`](../tests/), [`evals/`](../evals/), and
  [`scripts/run_quality_gate.py`](../scripts/run_quality_gate.py).
- “I need technical slide-level detail.” →
  [`repository-technical-outline.md`](repository-technical-outline.md).

---

## Final mental picture

```text
command
  -> validate/prepare data
  -> detect decline candidate
  -> create one bounded case
  -> model chooses one approved question
  -> deterministic tool calculates evidence receipts
  -> repeat within strict budgets
  -> model proposes a cited finish
  -> deterministic verifier approves, repairs, or refuses it
  -> write hashed reports and sanitized trace
  -> localhost app safely displays the result
  -> human decides what, if anything, happens next
```

That is WhyBack from start command to final boundary.
