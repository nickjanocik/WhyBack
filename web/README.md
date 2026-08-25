# WhyBack Investigator dashboard

This directory contains a thin, local review interface for WhyBack. The React
app does not calculate evidence or author recommendations. It visualizes the
versioned `report.json` and append-only `trace.jsonl` artifacts produced by the
Python system, while a localhost-only Node bridge can invoke one fixed,
credential-free CLI workflow.

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

## Interaction model

- Select an artifact collection and household to compare detector changes.
- Hover the weekly trend, open cited evidence, filter the immutable ledger, and
  replay the sanitized audit timeline.
- Use **Run demo** to execute this fixed command through an argv array (never a
  shell string):

  ```bash
  uv run whyback demo --customers <1-5> --backend scripted \
    --output-dir artifacts/local/dashboard
  ```

- Fresh output stays below the Git-ignored `artifacts/local/dashboard/` tree.
- The bridge binds to `127.0.0.1`, accepts no browser-supplied paths, has a
  120-second process boundary, and serializes demo execution.
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
