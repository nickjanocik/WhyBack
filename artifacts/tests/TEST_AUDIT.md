# WhyBack test audit

Overall result: **PASS**

Invocation: `aca229d5-35a3-4897-985c-5a66f868944f`
Started: `2026-08-25T01:36:35.051923Z`
Completed: `2026-08-25T01:36:58.881464Z`
Duration: `23.82960845902562 seconds`

## Reproducibility metadata

- Git: `76ac8de22fd313c4f5f1c2219b4375272f1996b2` on `codex/whyback-build` (dirty: `false`)
- Python: `3.12.14` (`CPython`)
- uv: `uv 0.12.5 (Homebrew 2026-08-14 aarch64-apple-darwin)`
- Platform: `macOS-26.3.1-arm64-arm-64bit`
- Lock SHA-256: `82894e4acdf443c2e44652bd3e22def210fc645de4ea93cb49d531709cee62f3`
- Source-tree SHA-256: `9bc89d240839bb283215686c9ea5ac8259b4d817f439db359288e141c64e989e`

```json
{
  "model_configuration": {
    "live_execution_permitted": false,
    "model": "gpt-5.6-sol",
    "openai_api_key_present": false,
    "reasoning_effort": "medium"
  },
  "source_dataset": {
    "manifest_path": "data/prepared/manifest.json",
    "manifest_sha256": "d5a361534a2a4c70a4eb94a65c21143f90b07e2df781d71aab3f0f72efc0f308",
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
    "covered_branches": 613,
    "covered_lines": 3210,
    "minimum_percent": 85.0,
    "missing_branches": 213,
    "missing_lines": 364,
    "num_branches": 826,
    "num_statements": 3574,
    "percent_covered": 86.88636363636364
  },
  "junit": {
    "duration_seconds": 18.97,
    "errors": 0,
    "failures": 0,
    "skipped": 1,
    "tests": 188
  }
}
```

## Steps

| Step | Required | Status | Exit | Duration |
| --- | ---: | ---: | ---: | ---: |
| coverage_configuration | True | passed | 0 | 0.0s |
| frozen_sync | True | passed | 0 | 0.010152958333492279s |
| ruff_format | True | passed | 0 | 0.02222541719675064s |
| ruff_lint | True | passed | 0 | 0.02453620871528983s |
| pyright | True | passed | 0 | 2.622246667277068s |
| pytest | True | passed | 0 | 19.328258417081088s |
| test_output_validation | True | passed | 0 | 0.0s |
| deterministic_evals | True | passed | 0 | 0.34357620775699615s |
| artifact_verification | True | passed | 0 | 0.6475644591264427s |
| official_artifact_verification | True | passed | 0 | 0.3609717912040651s |
| official_type_a_artifact_verification | True | passed | 0 | 0.3933401247486472s |

### coverage_configuration

Command: `(internal or skipped)`

Started: `2026-08-25T01:36:35.108998Z`
Completed: `2026-08-25T01:36:35.108998Z`

Stdout:

```text
Configured coverage minimum is 85.00%.

```

Stderr:

```text

```

### frozen_sync

Command: `uv sync --frozen --extra dev`

Started: `2026-08-25T01:36:35.110064Z`
Completed: `2026-08-25T01:36:35.120221Z`

Stdout:

```text

```

Stderr:

```text
Checked 46 packages in 0.98ms

```

### ruff_format

Command: `uv run ruff format --check .`

Started: `2026-08-25T01:36:35.121525Z`
Completed: `2026-08-25T01:36:35.143755Z`

Stdout:

```text
91 files already formatted

```

Stderr:

```text

```

### ruff_lint

Command: `uv run ruff check .`

Started: `2026-08-25T01:36:35.145157Z`
Completed: `2026-08-25T01:36:35.169699Z`

Stdout:

```text
All checks passed!

```

Stderr:

```text

```

### pyright

Command: `uv run pyright`

Started: `2026-08-25T01:36:35.171149Z`
Completed: `2026-08-25T01:36:37.793384Z`

Stdout:

```text
0 errors, 0 warnings, 0 informations

```

Stderr:

```text

```

### pytest

Command: `uv run pytest --cov=whyback --cov-branch --cov-report=json:artifacts/tests/coverage.json --junitxml=artifacts/tests/junit.xml`

Started: `2026-08-25T01:36:37.794838Z`
Completed: `2026-08-25T01:36:57.122971Z`

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
collected 188 items

tests/integration/test_cli_workflows.py ...                              [  1%]
tests/integration/test_demo_pipeline.py ......                           [  4%]
tests/integration/test_evaluation_cases.py .                             [  5%]
tests/integration/test_prepared_repository.py ....                       [  7%]
tests/live/test_openai_backend_live.py s                                 [  7%]
tests/orchestration/test_runner.py .............                         [ 14%]
tests/property/test_agent_invariants.py ............                     [ 21%]
tests/property/test_decline_properties.py .                              [ 21%]
tests/property/test_tool_contract_properties.py .                        [ 22%]
tests/unit/test_actions.py ........                                      [ 26%]
tests/unit/test_agent_backends.py ..............                         [ 34%]
tests/unit/test_audit_trace.py .......                                   [ 37%]
tests/unit/test_data_contracts.py .......                                [ 41%]
tests/unit/test_decline_detector.py .........                            [ 46%]
tests/unit/test_evals.py .........                                       [ 51%]
tests/unit/test_evidence_verifier.py ................................... [ 69%]
.                                                                        [ 70%]
tests/unit/test_fault_injection.py ...                                   [ 71%]
tests/unit/test_foundation.py ..                                         [ 72%]
tests/unit/test_promotion_coupon_peer.py ...                             [ 74%]
tests/unit/test_quality_scripts.py .........................             [ 87%]
tests/unit/test_reporting.py .......                                     [ 91%]
tests/unit/test_scripted_plans.py ....                                   [ 93%]
tests/unit/test_tool_contracts.py .....                                  [ 96%]
tests/unit/test_tool_registry.py ...                                     [ 97%]
tests/unit/test_trend_category_basket.py ....                            [100%]

- generated xml file: /Users/nickjanocik/Documents/WhyBack/artifacts/tests/junit.xml -
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.12.14-final-0 _______________

Coverage JSON written to file artifacts/tests/coverage.json
Required test coverage of 85.0% reached. Total coverage: 86.89%
=========================== short test summary info ============================
SKIPPED [1] tests/live/test_openai_backend_live.py:15: OPENAI_API_KEY is absent; live Responses execution was not attempted.
======================= 187 passed, 1 skipped in 19.01s ========================

```

Stderr:

```text

```

### test_output_validation

Command: `(internal or skipped)`

Started: `2026-08-25T01:36:57.128551Z`
Completed: `2026-08-25T01:36:57.128551Z`

Stdout:

```text
JUnit recorded 188 tests; branch-aware coverage is 86.88636363636364% across 826 branches (minimum 85.00%).

```

Stderr:

```text

```

### deterministic_evals

Command: `uv run python evals/run_evals.py artifacts/demo/evals/normalized_runs.json --json-output artifacts/tests/eval_report.json --markdown-output artifacts/tests/EVAL_REPORT.md`

Started: `2026-08-25T01:36:57.129660Z`
Completed: `2026-08-25T01:36:57.473238Z`

Stdout:

```text

```

Stderr:

```text

```

### artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/demo --json-output artifacts/tests/artifact_verification.json --allow-live-skipped`

Started: `2026-08-25T01:36:57.474936Z`
Completed: `2026-08-25T01:36:58.122501Z`

Stdout:

```text

```

Stderr:

```text

```

### official_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/official --json-output artifacts/tests/official_artifact_verification.json --allow-live-skipped`

Started: `2026-08-25T01:36:58.124161Z`
Completed: `2026-08-25T01:36:58.485137Z`

Stdout:

```text

```

Stderr:

```text

```

### official_type_a_artifact_verification

Command: `uv run python scripts/verify_artifacts.py artifacts/official-type-a --json-output artifacts/tests/official_type_a_artifact_verification.json`

Started: `2026-08-25T01:36:58.486672Z`
Completed: `2026-08-25T01:36:58.880016Z`

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
