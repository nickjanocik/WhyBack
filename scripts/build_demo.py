"""Generate WhyBack's committed deterministic and official-selection artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from whyback.demo import build_official_demo, build_synthetic_demo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=5)
    parser.add_argument("--demo-output", type=Path, default=Path("artifacts/demo"))
    parser.add_argument(
        "--official-output", type=Path, default=Path("artifacts/official")
    )
    parser.add_argument("--prepared-dir", type=Path, default=Path("data/prepared"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build synthetic controls and record the honest official live-run status."""

    arguments = _parser().parse_args(argv)
    synthetic = build_synthetic_demo(
        arguments.demo_output,
        customers=arguments.customers,
    )
    print(f"Synthetic manifest: {synthetic.manifest_path}")
    evaluation_directory = Path("artifacts/evals")
    evaluation_directory.mkdir(parents=True, exist_ok=True)
    evaluation = subprocess.run(
        (
            sys.executable,
            "evals/run_evals.py",
            str(arguments.demo_output / "evals" / "normalized_runs.json"),
            "--json-output",
            str(evaluation_directory / "eval_summary.json"),
            "--markdown-output",
            str(evaluation_directory / "EVAL_SUMMARY.md"),
        ),
        check=False,
    )
    if evaluation.returncode != 0:
        return evaluation.returncode
    print(f"Evaluation summary: {evaluation_directory / 'EVAL_SUMMARY.md'}")
    manifest = arguments.prepared_dir / "manifest.json"
    if not manifest.is_file():
        print(
            "Official selection skipped: prepared manifest is missing. Run "
            "`uv run whyback data prepare --full`."
        )
        return 0
    official = build_official_demo(
        arguments.prepared_dir,
        arguments.official_output,
        customers=arguments.customers,
        backend="openai",
    )
    print(f"Official manifest: {official.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
