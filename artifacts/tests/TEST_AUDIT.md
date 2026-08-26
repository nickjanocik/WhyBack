# WhyBack test audit

Overall result: **PASS**

Invocation: `6fa80ee2-5838-4725-bc14-afc88e0b0e86`
Started: `2026-08-26T05:38:05.416488Z`
Completed: `2026-08-26T05:39:39.920508Z`
Duration: `94.50448541715741 seconds`

## Reproducibility metadata

- Git: `4a12b2ac4d5c2c13a8c9d306dd85358a6f80d4a6` on `codex/whyback-build` (dirty: `true`)
- Python: `3.12.14` (`CPython`)
- uv: `uv 0.12.5 (Homebrew 2026-08-14 aarch64-apple-darwin)`
- Platform: `macOS-26.3.1-arm64-arm-64bit`
- Lock SHA-256: `33c6048fd1ed55d70a50dda82884dbdbc4ee2de3c24b6f54d9743011c89e0786`
- Source-tree SHA-256: `fe33e3e8e56c0dc8fbf4a09908bdc9eebd7a190ff6e9167f7b47410f4be4ff54`

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
    "manifest_sha256": "befa2c21a91913d10c4b42137149fbc1f383b3f510d0726b28fb2d59732b2fb0",
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
    "covered_branches": 925,
    "covered_lines": 4077,
    "minimum_percent": 85.0,
    "missing_branches": 285,
    "missing_lines": 445,
    "num_branches": 1210,
    "num_statements": 4522,
    "percent_covered": 87.26448011165387
  },
  "junit": {
    "duration_seconds": 78.302,
    "errors": 0,
    "failures": 0,
    "skipped": 1,
    "tests": 328
  }
}
```

## Steps

| Step | Required | Status | Exit | Duration |
| --- | ---: | ---: | ---: | ---: |
| coverage_configuration | True | passed | 0 | 0.0s |
| frozen_sync | True | passed | 0 | 0.6072857091203332s |
| web_frozen_install | True | passed | 0 | 1.6867130841128528s |
| ruff_format | True | passed | 0 | 0.5377548327669501s |
| ruff_lint | True | passed | 0 | 0.03858066629618406s |
| pyright | True | passed | 0 | 3.392789375036955s |
| web_quality | True | passed | 0 | 5.8364772093482316s |
| pytest | True | passed | 0 | 79.41050241701305s |
| test_output_validation | True | passed | 0 | 0.0s |
| deterministic_evals | True | passed | 0 | 0.5561798331327736s |
| artifact_verification | True | passed | 0 | 0.9892031247727573s |
| live_gemini_artifact_verification | True | passed | 0 | 0.4428448751568794s |
| official_artifact_verification | True | passed | 0 | 0.4069902077317238s |
| official_type_a_artifact_verification | True | passed | 0 | 0.47069562459364533s |

### coverage_configuration

Command: `(internal or skipped)`

Started: `2026-08-26T05:38:05.498202Z`
Completed: `2026-08-26T05:38:05.498202Z`

Stdout:

```text
Configured coverage minimum is 85.00%.

```

Stderr:

```text

```

### frozen_sync

Command: `uv sync --frozen --extra dev`

Started: `2026-08-26T05:38:05.500503Z`
Completed: `2026-08-26T05:38:06.107793Z`

Stdout:

```text

```

Stderr:

```text
Using CPython 3.12.14
Creating virtual environment at: .venv
   Building whyback @ file:///private/tmp/whyback-submission-clone.DqYcvi
      Built whyback @ file:///private/tmp/whyback-submission-clone.DqYcvi
Prepared 1 package in 229ms
Installed 55 packages in 283ms
 + annotated-doc==0.0.5
 + annotated-types==0.8.0
 + anyio==4.14.2
 + certifi==2026.7.22
 + cffi==2.1.1
 + charset-normalizer==3.5.1
 + coverage==7.15.4
 + cryptography==50.0.0
 + distro==1.9.0
 + duckdb==1.5.5
 + google-auth==2.57.0
 + google-genai==2.19.0
 + h11==0.16.0
 + httpcore==1.0.9
 + httpx==0.28.1
 + hypothesis==6.165.10
 + idna==3.19
 + iniconfig==2.3.0
 + jinja2==3.1.6
 + markdown-it-py==4.2.0
 + markupsafe==3.0.3
 + mdurl==0.1.2
 + nodeenv==1.10.0
 + numpy==2.5.2
 + packaging==26.3
 + pandas==3.0.5
 + pluggy==1.6.0
 + pyarrow==23.0.1
 + pyasn1==0.6.4
 + pyasn1-modules==0.4.2
 + pycparser==3.0
 + pydantic==2.13.4
 + pydantic-core==2.46.4
 + pygments==2.21.0
 + pyreadr==0.5.6
 + pyright==1.1.411
 + pytest==9.1.1
 + pytest-cov==7.1.0
 + pytest-timeout==2.4.0
 + python-dateutil==2.9.0.post0
 + pyyaml==6.0.3
 + requests==2.34.2
 + rich==14.3.4
 + ruff==0.16.4
 + shellingham==1.5.4
 + six==1.17.0
 + sniffio==1.3.1
 + sortedcontainers==2.4.0
 + tenacity==9.1.4
 + typer==0.27.1
 + typing-extensions==4.16.0
 + typing-inspection==0.4.4
 + urllib3==2.7.0
 + websockets==16.1.1
 + whyback==0.1.0 (from file:///private/tmp/whyback-submission-clone.DqYcvi)

```

### web_frozen_install

Command: `npm --prefix web ci --ignore-scripts`

Started: `2026-08-26T05:38:06.110544Z`
Completed: `2026-08-26T05:38:07.797256Z`

Stdout:

```text

added 246 packages, and audited 247 packages in 2s

59 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities

```

Stderr:

```text

```

### ruff_format

Command: `uv run ruff format --check .`

Started: `2026-08-26T05:38:07.800836Z`
Completed: `2026-08-26T05:38:08.338596Z`

Stdout:

```text
96 files already formatted

```

Stderr:

```text

```

### ruff_lint

Command: `uv run ruff check .`

Started: `2026-08-26T05:38:08.342202Z`
Completed: `2026-08-26T05:38:08.380793Z`

Stdout:

```text
All checks passed!

```

Stderr:

```text

```

### pyright

Command: `uv run pyright`

Started: `2026-08-26T05:38:08.383527Z`
Completed: `2026-08-26T05:38:11.776308Z`

Stdout:

```text
0 errors, 0 warnings, 0 informations

```

Stderr:

```text

```

### web_quality

Command: `npm --prefix web run check`

Started: `2026-08-26T05:38:11.779015Z`
Completed: `2026-08-26T05:38:17.615463Z`

Stdout:

```text

> whyback-dashboard@0.1.0 check
> npm run lint && npm run test && npm run build


> whyback-dashboard@0.1.0 lint
> eslint .


> whyback-dashboard@0.1.0 test
> vitest run src && node --test server/*.test.mjs


 RUN  v4.1.11 /private/tmp/whyback-submission-clone.DqYcvi/web


 Test Files  2 passed (2)
      Tests  18 passed (18)
   Start at  00:38:14
   Duration  873ms (transform 90ms, setup 108ms, import 192ms, tests 302ms, environment 522ms)

✔ loads collection summaries from canonical report artifacts (9.18ms)
✔ loads a report and emits only allow-listed trace detail (3.842583ms)
✔ rejects traversal-shaped IDs and non-allow-listed artifact files (2.982ms)
✔ loads preserved flat-layout boundary artifacts (4.002167ms)
✔ discovers and loads preserved Live Gemini collections newest first (39.980125ms)
✔ rejects unsafe dynamic collections and files without affecting fixed history (11.450792ms)
✔ publishes the supported inclusive demo customer range (1.279541ms)
✔ rejects demo customer counts outside the range or not integers (0.0615ms)
✔ every web source file and named function has leading plain-English documentation (20.926125ms)
✔ accepts same-origin JSON mutation requests (0.720417ms)
✔ rejects non-JSON and cross-site mutation requests (0.109666ms)
✔ allows only localhost Host headers (0.2215ms)
✔ publishes secret-free live readiness and requires official prepared data (5.188ms)
✔ validates official prepared data without passing the Gemini credential (0.939042ms)
✔ fails closed without live readiness before invoking the run manager (0.250084ms)
✔ accepts only a customer count from the browser (0.110833ms)
✔ constructs only the fixed Gemini command in a unique live collection (0.206833ms)
✔ accepts only reconciled manifests that prove a live Gemini execution (0.191542ms)
✔ uses bounded live timeouts and the configured Gemini model (0.105375ms)
✔ runs the fixed Gemini process and accepts only verified owned output (17.631917ms)
✔ terminates a timed-out live process before rejecting (2.298792ms)
✔ keeps a post-spawn process error failed until the child closes (0.51175ms)
✔ does not start artifact verification after shutdown begins (4.954125ms)
✔ shutdown terminates an active live child before releasing it (0.819916ms)
✔ dashboard shutdown closes the listener, stops processes, and exits once (0.191125ms)
✔ dashboard shutdown performs its final process drain after HTTP close (0.267958ms)
✔ derives only canonical version-4 UUID collection paths (0.99875ms)
✔ resolves only real owned run directories with an exact marker (10.042792ms)
✔ resolves a terminal collection only after verification and rejects later mutation (18.7765ms)
✔ rejects symlinked run roots, run directories, and ownership markers (4.659291ms)
✔ discovers owned Live Gemini collections newest first (14.264375ms)
✔ publishes only newline-terminated JSONL records and resumes a partial line (10.691375ms)
✔ allow-lists display details and omits raw, sensitive, and reasoning fields (3.91225ms)
✔ reads only real customer trace sources and ignores demo-control or symlink sources (4.742042ms)
✔ ignores unowned and malformed-marker staging directories (4.870375ms)
✔ returns monotonic reader deltas without replaying previously consumed lines (11.103125ms)
✔ does not consume valid trace batches when another source is malformed (4.9225ms)
✔ streams only from an explicit owned live-run directory (6.6505ms)
✔ rejects an explicit trace root outside the repository (3.937416ms)
✔ manager ignores staging directories that existed before its run (12.766834ms)
✔ a successful published scan clears a transient staging warning (9.340292ms)
✔ manager reports its capacity and drops only the oldest retained events (8.773ms)
✔ manager gates concurrent starts, exposes cursor deltas, and releases after completion (14.746292ms)
✔ manager preserves partial events, records failure, and releases the running gate (12.824166ms)
✔ manager carries a unique live descriptor through execution and status (6.756791ms)
✔ loads the repository-root environment without replacing an exported Gemini key (0.706917ms)
✔ tolerates only a missing repository environment file (0.221167ms)
✔ loads the environment before dynamically importing and starting the server (0.685458ms)
ℹ tests 48
ℹ suites 0
ℹ pass 48
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 198.905542

> whyback-dashboard@0.1.0 build
> tsc -b && vite build

vite v8.2.2 building client environment for production...
transforming...
✓ 2217 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.68 kB │ gzip:   0.39 kB
dist/assets/index-BUtaiHMF.css   42.82 kB │ gzip:   8.77 kB
dist/assets/index-B0BpA1sg.js   375.62 kB │ gzip: 117.29 kB

✓ built in 321ms

```

Stderr:

```text

```

### pytest

Command: `uv run pytest --cov=whyback --cov-branch --cov-report=json:artifacts/tests/coverage.json --junitxml=artifacts/tests/junit.xml`

Started: `2026-08-26T05:38:17.618386Z`
Completed: `2026-08-26T05:39:37.028416Z`

Stdout:

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: /private/tmp/whyback-submission-clone.DqYcvi
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, timeout-2.4.0, anyio-4.14.2, hypothesis-6.165.10
timeout: 30.0s
timeout method: signal
timeout func_only: False
collected 328 items

tests/integration/test_cli_workflows.py .......                          [  2%]
tests/integration/test_demo_pipeline.py ..............                   [  6%]
tests/integration/test_evaluation_cases.py .                             [  6%]
tests/integration/test_prepared_repository.py ....                       [  7%]
tests/live/test_gemini_backend_live.py s                                 [  8%]
tests/orchestration/test_runner.py ...............                       [ 12%]
tests/property/test_agent_invariants.py ............                     [ 16%]
tests/property/test_decline_properties.py .                              [ 16%]
tests/property/test_tool_contract_properties.py .                        [ 17%]
tests/unit/test_actions.py ........                                      [ 19%]
tests/unit/test_agent_backends.py .....................                  [ 25%]
tests/unit/test_audit_trace.py .........                                 [ 28%]
tests/unit/test_data_contracts.py .......                                [ 30%]
tests/unit/test_decline_detector.py .........                            [ 33%]
tests/unit/test_demo_limits.py .......                                   [ 35%]
tests/unit/test_documentation_coverage.py ..                             [ 36%]
tests/unit/test_evals.py ...................                             [ 42%]
tests/unit/test_evidence_verifier.py ................................... [ 52%]
........................................................................ [ 74%]
...                                                                      [ 75%]
tests/unit/test_fault_injection.py ...                                   [ 76%]
tests/unit/test_foundation.py .....                                      [ 78%]
tests/unit/test_promotion_coupon_peer.py .....                           [ 79%]
tests/unit/test_quality_scripts.py ..................................    [ 89%]
tests/unit/test_reporting.py ............                                [ 93%]
tests/unit/test_scripted_plans.py ....                                   [ 94%]
tests/unit/test_tool_contracts.py .....                                  [ 96%]
tests/unit/test_tool_registry.py ...                                     [ 97%]
tests/unit/test_trend_category_basket.py .........                       [100%]

- generated xml file: /private/tmp/whyback-submission-clone.DqYcvi/artifacts/tests/junit.xml -
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.12.14-final-0 _______________

Coverage JSON written to file artifacts/tests/coverage.json
Required test coverage of 85.0% reached. Total coverage: 87.26%
=========================== short test summary info ============================
SKIPPED [1] tests/live/test_gemini_backend_live.py:44: GEMINI_API_KEY is absent; live Gemini execution was not attempted.
================== 327 passed, 1 skipped in 78.34s (0:01:18) ===================

```

Stderr:

```text

```

### test_output_validation

Command: `(internal or skipped)`

Started: `2026-08-26T05:39:37.036797Z`
Completed: `2026-08-26T05:39:37.036797Z`

Stdout:

```text
JUnit recorded 328 tests; branch-aware coverage is 87.26448011165387% across 1210 branches (minimum 85.00%).

```

Stderr:

```text

```

### deterministic_evals

Command: `uv run python evals/run_evals.py artifacts/demo/evals/normalized_runs.json --json-output artifacts/tests/eval_report.json --markdown-output artifacts/tests/EVAL_REPORT.md`

Started: `2026-08-26T05:39:37.039392Z`
Completed: `2026-08-26T05:39:37.595575Z`

Stdout:

```text

```

Stderr:

```text

```

### artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/demo --json-output artifacts/tests/artifact_verification.json --allow-live-skipped`

Started: `2026-08-26T05:39:37.598450Z`
Completed: `2026-08-26T05:39:38.587654Z`

Stdout:

```text

```

Stderr:

```text

```

### live_gemini_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/live-gemini-synthetic-failure --json-output artifacts/tests/live_gemini_artifact_verification.json`

Started: `2026-08-26T05:39:38.591033Z`
Completed: `2026-08-26T05:39:39.033882Z`

Stdout:

```text

```

Stderr:

```text

```

### official_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/official --json-output artifacts/tests/official_artifact_verification.json --allow-live-skipped`

Started: `2026-08-26T05:39:39.036888Z`
Completed: `2026-08-26T05:39:39.443886Z`

Stdout:

```text

```

Stderr:

```text

```

### official_type_a_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/official-type-a --json-output artifacts/tests/official_type_a_artifact_verification.json`

Started: `2026-08-26T05:39:39.446862Z`
Completed: `2026-08-26T05:39:39.917566Z`

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
