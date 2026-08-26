"""Summarize WhyBack operational health or compare two compatible run cohorts."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from whyback.observability.operations import (
    DEFAULT_DISTANCE_THRESHOLD,
    DEFAULT_MINIMUM_RUNS,
    DriftStatus,
    OperationalInputStatus,
    compare_operational_cohorts,
    summarize_operational_health,
)


def _minimum_runs(value: str) -> int:
    """Parse the hard minimum sample-size safeguard for argparse."""

    parsed = int(value)
    if parsed < DEFAULT_MINIMUM_RUNS:
        raise argparse.ArgumentTypeError(f"must be at least {DEFAULT_MINIMUM_RUNS}")
    return parsed


def _unit_interval(value: str) -> float:
    """Parse a finite drift threshold inside the closed unit interval."""

    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be finite and between 0 and 1")
    return parsed


def _add_output_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared optional JSON destination to one subcommand."""

    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Write JSON to this path instead of stdout.",
    )


def _parser() -> argparse.ArgumentParser:
    """Build the read-only operational audit command parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    summarize = commands.add_parser(
        "summarize",
        help="Aggregate operational health below one artifact root.",
    )
    summarize.add_argument(
        "artifact_root",
        type=Path,
        help="Directory searched recursively, or one explicit trace.jsonl file.",
    )
    _add_output_argument(summarize)

    compare = commands.add_parser(
        "compare",
        help="Compare compatible baseline and current artifact roots.",
    )
    compare.add_argument("baseline_root", type=Path)
    compare.add_argument("current_root", type=Path)
    compare.add_argument(
        "--minimum-runs",
        type=_minimum_runs,
        default=DEFAULT_MINIMUM_RUNS,
        help="Minimum observations required in each cohort and metric.",
    )
    compare.add_argument(
        "--distance-threshold",
        type=_unit_interval,
        default=DEFAULT_DISTANCE_THRESHOLD,
        help="Inclusive KS/TV distance boundary for detected drift.",
    )
    compare.add_argument(
        "--require-assessment",
        action="store_true",
        help="Return nonzero unless the compatible comparison is stable.",
    )
    _add_output_argument(compare)
    return parser


def _protected_root(path: Path) -> Path:
    """Resolve the artifact directory protected from audit-output writes."""

    return (path if path.is_dir() else path.parent).resolve()


def _validate_output(output: Path | None, inputs: Sequence[Path]) -> None:
    """Refuse symlinked or input-tree output destinations."""

    if output is None:
        return
    absolute = output.absolute()
    if absolute.is_symlink():
        raise ValueError("Audit output cannot traverse a symlink")
    resolved = output.resolve()
    if any(resolved.is_relative_to(_protected_root(root)) for root in inputs):
        raise ValueError("Audit output must be outside every input artifact root")


def _write_json(document: object, output: Path | None) -> None:
    """Write canonical JSON to stdout or atomically to a validated path."""

    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(rendered)
            stream.flush()
            temporary = Path(stream.name)
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected audit and return a gate-friendly exit code."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "summarize":
            _validate_output(arguments.json_output, (arguments.artifact_root,))
            report = summarize_operational_health(arguments.artifact_root)
            _write_json(
                report.model_dump(mode="json"),
                arguments.json_output,
            )
            return 0 if report.status is OperationalInputStatus.READY else 1

        _validate_output(
            arguments.json_output,
            (arguments.baseline_root, arguments.current_root),
        )
        report = compare_operational_cohorts(
            arguments.baseline_root,
            arguments.current_root,
            minimum_runs=arguments.minimum_runs,
            distance_threshold=arguments.distance_threshold,
        )
        _write_json(report.model_dump(mode="json"), arguments.json_output)
        if arguments.require_assessment and report.status is not DriftStatus.STABLE:
            return 1
        return 0
    except (OSError, RuntimeError, ValueError):
        # The caller already supplied the path. Avoid echoing customer-bearing paths
        # or parser/provider details back into a portable operational transcript.
        print(
            "Operational audit failed because its input or output was unsafe.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
