# WhyBack test audit

Overall result: **PASS**

Invocation: `e060ce7e-69ea-4a5d-b76e-ffd36051d53e`
Started: `2026-08-26T07:35:07.098801Z`
Completed: `2026-08-26T07:36:28.227179Z`
Duration: `81.12874762481079 seconds`

## Reproducibility metadata

- Git: `b8ef9f4b4f8a0afeddf94f5be287fd68945a9ec0` on `codex/whyback-build` (dirty: `true`)
- Python: `3.12.14` (`CPython`)
- uv: `uv 0.12.5 (Homebrew 2026-08-14 aarch64-apple-darwin)`
- Platform: `macOS-26.3.1-arm64-arm-64bit`
- Lock SHA-256: `33c6048fd1ed55d70a50dda82884dbdbc4ee2de3c24b6f54d9743011c89e0786`
- Source-tree SHA-256: `dcc652e37408928e59b710ca414112b7d3461ae71a114c5a849346090dfdd54f`

```json
{
  "model_configuration": {
    "gemini_api_key_present": false,
    "live_execution_permitted": false,
    "model": "gemini-3.7-flash",
    "thinking_level": "medium"
  },
  "source_dataset": {
    "manifest_path": "data/prepared/manifest.json",
    "manifest_sha256": "fba76046cf6f772a1c2ecc858d08d29ceac4bd2c275f1749a698f9bfa5138785",
    "prepared_hashes": {
      "baskets.parquet": "75fcdc22a7ffbe99a28d2d33164420be0417c24f22329a123a7677b4b3e28ea4",
      "campaign_descriptions.parquet": "84f7fa81c8a73659a9f0e4136b0ac99a1cac5f0c72fadae067346832acbdf352",
      "campaigns.parquet": "664d2cdfdfa52d4902bb2002c3387ccd69f01392a0b02e22721ad9aa9cade3d6",
      "coupon_redemptions.parquet": "c3f89bd018c5e32c983a7a970774010dbe5c4ed13eec93ed50f6befcf93bf00e",
      "coupons.parquet": "741b1f9aba167760e6b417bb0c77ec4631b057e731f052b478e4b3dc1f4f2575",
      "demographics.parquet": "0d6809a02a9907a29f951d801f687517f42b6efe1897c6810be651f37f9caeb8",
      "household_week.parquet": "c73553e7be44749ca8e536f3ddd22e2c762dbdf025bea492959c93bd3f5439df",
      "products.parquet": "e7d9b1dede14dd2848695c6b784f3d42321c977fb665b09fbadab9327e7b9592",
      "promotion_state.parquet": "d586f7ec968d384cdf9e08e9a5562aa992b4544569b4252f9998d0cd8a7b6fac",
      "transactions.parquet": "08bc0f6cfaa064533f7e910d4c2b3bde0f42901b197f4077ccc16fb85d74c797"
    },
    "prepared_table_count": 10,
    "source_commit": "5b5d06192b9856edd04e4d405787af2f2e4a1fef",
    "source_file_count": 8,
    "source_hashes": {
      "campaign_descriptions.rda": "601bd17ea1a6de92cc288f393164813fbaf293b997d44054dcf1f3ebbe8dacee",
      "campaigns.rda": "33c7b3dc1bc722d465f97416fb1327c6a9a640190e464c73e354bce8c001a772",
      "coupon_redemptions.rda": "4b68148175ed19300bb2615d68d1a0300a5f971db3240819ab5d92e5919e1598",
      "coupons.rda": "4d87effce5b8813c0934b581a83292707347577743320ca746878de89cc16f34",
      "demographics.rda": "8b80455bc841003b64e47f5e5c2221f6093b995e923d59e72a1f852c7e268980",
      "products.rda": "a80c6df33623b4af296ae9f317a6647e369db7e8ce7e7baed0e1bf44b9d979e5",
      "promotions.rds": "15a729fdad31b10d3afedb058da31bcd6e9e68cb0207a43b3121264cd80198ba",
      "transactions.rds": "1fa0700033f1e5d9bb6b09e2be063d8d68474d346e95c50f2833e09d083e0007"
    },
    "source_repository": "bradleyboehmke/completejourney",
    "status": "available"
  }
}
```

## Parsed test results

```json
{
  "coverage": {
    "covered_branches": 924,
    "covered_lines": 4077,
    "minimum_percent": 85.0,
    "missing_branches": 286,
    "missing_lines": 445,
    "num_branches": 1210,
    "num_statements": 4522,
    "percent_covered": 87.2470341939986
  },
  "junit": {
    "duration_seconds": 64.038,
    "errors": 0,
    "failures": 0,
    "skipped": 1,
    "tests": 336
  }
}
```

## Steps

| Step | Required | Status | Exit | Duration |
| --- | ---: | ---: | ---: | ---: |
| coverage_configuration | True | passed | 0 | 0.0s |
| frozen_sync | True | passed | 0 | 0.015816291328519583s |
| web_frozen_install | True | passed | 0 | 2.9064287077635527s |
| ruff_format | True | passed | 0 | 0.05278620822355151s |
| ruff_lint | True | passed | 0 | 0.027974499855190516s |
| pyright | True | passed | 0 | 3.326947999652475s |
| web_quality | True | passed | 0 | 7.197911332827061s |
| pytest | True | passed | 0 | 64.48870454123244s |
| test_output_validation | True | passed | 0 | 0.0s |
| deterministic_evals | True | passed | 0 | 0.5039671249687672s |
| artifact_verification | True | passed | 0 | 0.9069277080707252s |
| live_gemini_artifact_verification | True | passed | 0 | 0.4040961251594126s |
| official_artifact_verification | True | passed | 0 | 0.36107891611754894s |
| official_type_a_artifact_verification | True | passed | 0 | 0.4315583328716457s |

### coverage_configuration

Command: `(internal or skipped)`

Started: `2026-08-26T07:35:07.542402Z`
Completed: `2026-08-26T07:35:07.542402Z`

Stdout:

```text
Configured coverage minimum is 85.00%.

```

Stderr:

```text

```

### frozen_sync

Command: `uv sync --frozen --extra dev`

Started: `2026-08-26T07:35:07.547199Z`
Completed: `2026-08-26T07:35:07.563019Z`

Stdout:

```text

```

Stderr:

```text
Checked 55 packages in 3ms

```

### web_frozen_install

Command: `npm --prefix web ci --ignore-scripts`

Started: `2026-08-26T07:35:07.566243Z`
Completed: `2026-08-26T07:35:10.472676Z`

Stdout:

```text

added 246 packages, and audited 247 packages in 3s

59 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities

```

Stderr:

```text

```

### ruff_format

Command: `uv run ruff format --check .`

Started: `2026-08-26T07:35:10.476465Z`
Completed: `2026-08-26T07:35:10.529257Z`

Stdout:

```text
96 files already formatted

```

Stderr:

```text

```

### ruff_lint

Command: `uv run ruff check .`

Started: `2026-08-26T07:35:10.532814Z`
Completed: `2026-08-26T07:35:10.560794Z`

Stdout:

```text
All checks passed!

```

Stderr:

```text

```

### pyright

Command: `uv run pyright`

Started: `2026-08-26T07:35:10.564361Z`
Completed: `2026-08-26T07:35:13.891300Z`

Stdout:

```text
0 errors, 0 warnings, 0 informations

```

Stderr:

```text

```

### web_quality

Command: `npm --prefix web run check`

Started: `2026-08-26T07:35:13.894929Z`
Completed: `2026-08-26T07:35:21.092811Z`

Stdout:

```text

> whyback-dashboard@0.1.0 check
> npm run lint && npm run test && npm run build


> whyback-dashboard@0.1.0 lint
> eslint .


> whyback-dashboard@0.1.0 test
> vitest run src && node --test server/*.test.mjs


 RUN  v4.1.11 /Users/nickjanocik/Documents/WhyBack/web


 Test Files  3 passed (3)
      Tests  23 passed (23)
   Start at  02:35:16
   Duration  2.27s (transform 176ms, setup 364ms, import 497ms, tests 1.64s, environment 1.17s)

✔ loads summaries only from sealed CLI artifacts (28.132209ms)
✔ loads a report and emits only allow-listed trace detail (9.252833ms)
✔ rejects traversal-shaped IDs and non-allow-listed artifact files (7.000709ms)
✔ does not expose bundled examples or boundary fixtures (2.365ms)
✔ discovers and loads preserved Live Gemini collections newest first (18.351208ms)
✔ rejects unsafe dynamic collections and files (9.204542ms)
✔ publishes the supported inclusive demo customer range (1.544167ms)
✔ rejects demo customer counts outside the range or not integers (0.08575ms)
✔ every web source file and named function has leading plain-English documentation (25.446375ms)
✔ accepts same-origin JSON mutation requests (0.71375ms)
✔ rejects non-JSON and cross-site mutation requests (0.053375ms)
✔ allows only localhost Host headers (0.06125ms)
✔ publishes secret-free live readiness and requires official prepared data (5.750583ms)
✔ validates official prepared data without passing the Gemini credential (0.774208ms)
✔ fails closed without live readiness before invoking the run manager (0.218208ms)
✔ accepts only a customer count from the browser (0.082584ms)
✔ constructs only the fixed Gemini command in a unique live collection (0.199625ms)
✔ accepts only reconciled manifests that prove a live Gemini execution (0.188125ms)
✔ uses bounded live timeouts and the configured Gemini model (0.08025ms)
✔ publishes independently verified terminal output after a nonzero CLI exit (17.165083ms)
✔ rejects a nonzero CLI exit when its terminal output is missing (0.676875ms)
✔ does not seal terminal output when independent verification fails (4.493459ms)
✔ terminates a timed-out live process before rejecting (1.885041ms)
✔ keeps a post-spawn process error failed until the child closes (0.445375ms)
✔ does not start artifact verification after shutdown begins (5.319291ms)
✔ shutdown terminates an active live child before releasing it (0.572875ms)
✔ dashboard shutdown closes the listener, stops processes, and exits once (0.149083ms)
✔ dashboard shutdown performs its final process drain after HTTP close (0.212458ms)
✔ derives only canonical version-4 UUID collection paths (1.125958ms)
✔ resolves only real owned run directories with an exact marker (8.587416ms)
✔ resolves a terminal collection only after verification and rejects later mutation (19.228333ms)
✔ rejects symlinked run roots, run directories, and ownership markers (5.069708ms)
✔ discovers owned Live Gemini collections newest first (10.538333ms)
✔ publishes only newline-terminated JSONL records and resumes a partial line (10.418667ms)
✔ allow-lists display details and omits raw, sensitive, and reasoning fields (4.927459ms)
✔ reads only real customer trace sources and ignores demo-control or symlink sources (4.881834ms)
✔ ignores unowned and malformed-marker staging directories (5.609459ms)
✔ returns monotonic reader deltas without replaying previously consumed lines (9.823875ms)
✔ does not consume valid trace batches when another source is malformed (4.319416ms)
✔ streams only from an explicit owned live-run directory (4.067833ms)
✔ rejects an explicit trace root outside the repository (3.143583ms)
✔ manager ignores staging directories that existed before its run (13.037208ms)
✔ a successful published scan clears a transient staging warning (8.058625ms)
✔ manager reports its capacity and drops only the oldest retained events (8.601541ms)
✔ manager gates concurrent starts, exposes cursor deltas, and releases after completion (16.304792ms)
✔ manager preserves partial events, records failure, and releases the running gate (15.061583ms)
✔ manager carries a unique live descriptor through execution and status (6.97275ms)
✔ loads the repository-root environment without replacing an exported Gemini key (0.848584ms)
✔ tolerates only a missing repository environment file (0.228708ms)
✔ loads the environment before dynamically importing and starting the server (0.709ms)
ℹ tests 50
ℹ suites 0
ℹ pass 50
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 201.187459

> whyback-dashboard@0.1.0 build
> tsc -b && vite build

vite v8.2.2 building client environment for production...
transforming...
✓ 2217 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.68 kB │ gzip:   0.40 kB
dist/assets/index-DpCn88cP.css   44.57 kB │ gzip:   8.96 kB
dist/assets/index-BaZSFxmQ.js   378.34 kB │ gzip: 118.11 kB

✓ built in 369ms

```

Stderr:

```text

```

### pytest

Command: `uv run pytest --cov=whyback --cov-branch --cov-report=json:artifacts/tests/coverage.json --junitxml=artifacts/tests/junit.xml`

Started: `2026-08-26T07:35:21.097136Z`
Completed: `2026-08-26T07:36:25.585474Z`

Stdout:

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/nickjanocik/Documents/WhyBack
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, timeout-2.4.0, anyio-4.14.2, hypothesis-6.165.10
timeout: 30.0s
timeout method: signal
timeout func_only: False
collected 336 items

tests/integration/test_cli_workflows.py .......                          [  2%]
tests/integration/test_demo_pipeline.py ..............                   [  6%]
tests/integration/test_evaluation_cases.py .                             [  6%]
tests/integration/test_prepared_repository.py ....                       [  7%]
tests/live/test_gemini_backend_live.py s                                 [  8%]
tests/orchestration/test_runner.py ...............                       [ 12%]
tests/property/test_agent_invariants.py ............                     [ 16%]
tests/property/test_decline_properties.py .                              [ 16%]
tests/property/test_tool_contract_properties.py .                        [ 16%]
tests/unit/test_actions.py ........                                      [ 19%]
tests/unit/test_agent_backends.py .....................                  [ 25%]
tests/unit/test_audit_trace.py .........                                 [ 27%]
tests/unit/test_data_contracts.py .......                                [ 30%]
tests/unit/test_decline_detector.py .........                            [ 32%]
tests/unit/test_demo_limits.py .......                                   [ 34%]
tests/unit/test_documentation_coverage.py ..                             [ 35%]
tests/unit/test_evals.py ...................                             [ 41%]
tests/unit/test_evidence_verifier.py ................................... [ 51%]
........................................................................ [ 72%]
...                                                                      [ 73%]
tests/unit/test_fault_injection.py ...                                   [ 74%]
tests/unit/test_foundation.py .....                                      [ 76%]
tests/unit/test_promotion_coupon_peer.py .....                           [ 77%]
tests/unit/test_quality_scripts.py ..................................... [ 88%]
.....                                                                    [ 90%]
tests/unit/test_reporting.py ............                                [ 93%]
tests/unit/test_scripted_plans.py ....                                   [ 94%]
tests/unit/test_tool_contracts.py .....                                  [ 96%]
tests/unit/test_tool_registry.py ...                                     [ 97%]
tests/unit/test_trend_category_basket.py .........                       [100%]

- generated xml file: /Users/nickjanocik/Documents/WhyBack/artifacts/tests/junit.xml -
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.12.14-final-0 _______________

Coverage JSON written to file artifacts/tests/coverage.json
Required test coverage of 85.0% reached. Total coverage: 87.25%
=========================== short test summary info ============================
SKIPPED [1] tests/live/test_gemini_backend_live.py:44: GEMINI_API_KEY is absent; live Gemini execution was not attempted.
================== 335 passed, 1 skipped in 64.06s (0:01:04) ===================

```

Stderr:

```text

```

### test_output_validation

Command: `(internal or skipped)`

Started: `2026-08-26T07:36:25.595617Z`
Completed: `2026-08-26T07:36:25.595617Z`

Stdout:

```text
JUnit recorded 336 tests; branch-aware coverage is 87.2470341939986% across 1210 branches (minimum 85.00%).

```

Stderr:

```text

```

### deterministic_evals

Command: `uv run python evals/run_evals.py artifacts/demo/evals/normalized_runs.json --json-output artifacts/tests/eval_report.json --markdown-output artifacts/tests/EVAL_REPORT.md`

Started: `2026-08-26T07:36:25.599098Z`
Completed: `2026-08-26T07:36:26.103069Z`

Stdout:

```text

```

Stderr:

```text

```

### artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/demo --json-output artifacts/tests/artifact_verification.json --allow-live-skipped`

Started: `2026-08-26T07:36:26.106964Z`
Completed: `2026-08-26T07:36:27.013894Z`

Stdout:

```text

```

Stderr:

```text

```

### live_gemini_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/live-gemini-synthetic-failure --json-output artifacts/tests/live_gemini_artifact_verification.json`

Started: `2026-08-26T07:36:27.019092Z`
Completed: `2026-08-26T07:36:27.423196Z`

Stdout:

```text

```

Stderr:

```text

```

### official_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/official --json-output artifacts/tests/official_artifact_verification.json --allow-live-skipped`

Started: `2026-08-26T07:36:27.426897Z`
Completed: `2026-08-26T07:36:27.787982Z`

Stdout:

```text

```

Stderr:

```text

```

### official_type_a_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/official-type-a --json-output artifacts/tests/official_type_a_artifact_verification.json`

Started: `2026-08-26T07:36:27.791792Z`
Completed: `2026-08-26T07:36:28.223354Z`

Stdout:

```text

```

Stderr:

```text

```

## Failure observations

None.

## Prior invocations retained

| Invocation | Started | Result | Failures |
| --- | --- | ---: | --- |
| `fc0fa366-baa1-4eff-9c56-960605dd237d` | `2026-08-25T01:30:51.640542Z` | fail | frozen_sync, ruff_format, ruff_lint, pyright, pytest, test_output_validation, deterministic_evals, artifact_verification, official_artifact_verification, official_type_a_artifact_verification |
| `ae802628-c7ed-4717-9d83-7ecd55338ab1` | `2026-08-25T01:32:17.746590Z` | pass | none |
| `f7e88cde-a8d6-4aa0-8ac5-d784f7e0daf1` | `2026-08-25T01:35:28.946983Z` | pass | none |
| `aca229d5-35a3-4897-985c-5a66f868944f` | `2026-08-25T01:36:35.051923Z` | pass | none |
| `b7b40f9a-b4f2-4adb-a5b1-a977544cf837` | `2026-08-25T04:51:31.091353Z` | pass | none |
| `2f6ea3ac-d8ca-42f6-b33f-0bd48e49d628` | `2026-08-25T05:11:29.482033Z` | pass | none |
| `f8211cb7-5144-4d6f-8b72-7364dbb01ac9` | `2026-08-25T05:31:03.766262Z` | pass | none |
| `d6261b54-afe1-4f7a-b7f2-b4742391a499` | `2026-08-25T17:54:22.395593Z` | pass | none |
| `bae4b901-5a31-4b17-bc60-897a368b93b3` | `2026-08-25T18:13:45.002272Z` | pass | none |
| `5aa9cf8c-3d51-4026-9850-fc1e91143c77` | `2026-08-25T18:36:16.939626Z` | pass | none |
| `747c8cb7-2f3e-4d8d-98a2-9f74397af2b7` | `2026-08-26T02:23:56.682072Z` | pass | none |
| `4643d602-6961-4bcd-a26e-880d6446c226` | `2026-08-26T02:29:16.282613Z` | pass | none |
| `6fa80ee2-5838-4725-bc14-afc88e0b0e86` | `2026-08-26T05:38:05.416488Z` | pass | none |
| `b96178c2-8b6a-4106-9ae1-81082213c6dc` | `2026-08-26T05:49:33.117663Z` | pass | none |
| `7cd9cc55-9d7d-493d-9c38-2e70d2a097c6` | `2026-08-26T05:56:50.830318Z` | pass | none |
| `f453ff84-a4e3-4d0c-bd79-9853bda464c4` | `2026-08-26T06:02:00.786815Z` | pass | none |
| `1a6a3727-c07f-48cf-83b2-5aa2e85609b5` | `2026-08-26T06:25:54.755737Z` | fail | pytest, test_output_validation |
| `202c1022-c0f0-4fe6-a6b1-9f7918a0ecd2` | `2026-08-26T06:54:29.399657Z` | pass | none |
| `5cc7a909-6cc8-4b4a-87b6-f3790addc37c` | `2026-08-26T07:26:33.364017Z` | pass | none |
