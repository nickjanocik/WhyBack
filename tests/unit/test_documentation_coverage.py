"""Regression tests for plain-English Python file and callable documentation."""

from __future__ import annotations

import ast
import re
from pathlib import Path

PYTHON_ROOTS = ("src", "scripts", "evals", "tests")
COMMENTED_DECLARATIVE_FILES = {
    ".env.example": "#",
    ".github/workflows/ci.yml": "#",
    ".github/workflows/security.yml": "#",
    "Makefile": "#",
    "configs/actions.yaml": "#",
    "configs/app.toml": "#",
    "evals/scenarios.yaml": "#",
    "pyproject.toml": "#",
    "src/whyback/reporting/templates/report.html.j2": "{#",
    "src/whyback/reporting/templates/report.md.j2": "{#",
    "src/whyback/reporting/templates/trace.html.j2": "{#",
}
PLAIN_ENGLISH_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _is_plain_english_explanation(value: str | None) -> bool:
    """Return whether text contains at least three ordinary English-like words."""

    return value is not None and len(PLAIN_ENGLISH_WORD.findall(value)) >= 3


def _leading_comment(contents: str, prefix: str) -> str | None:
    """Extract the first declarative-file comment without parsing its data format."""

    if not contents.startswith(prefix):
        return None
    if prefix == "#":
        comment_lines: list[str] = []
        for line in contents.splitlines():
            if not line.startswith("#"):
                break
            comment_lines.append(line.removeprefix("#"))
        return " ".join(comment_lines)
    closing = contents.find("#}", len(prefix))
    return None if closing < 0 else contents[len(prefix) : closing]


def _undocumented_boundaries(repository_root: Path) -> tuple[str, ...]:
    """List Python modules, classes, and callables that have no docstring."""

    missing: list[str] = []
    for relative_root in PYTHON_ROOTS:
        for path in sorted((repository_root / relative_root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(repository_root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            if not _is_plain_english_explanation(ast.get_docstring(tree)):
                missing.append(f"{relative}:1:<module>")
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not _is_plain_english_explanation(ast.get_docstring(node)):
                    missing.append(f"{relative}:{node.lineno}:{node.name}")
    return tuple(missing)


def test_every_python_file_class_and_callable_explains_its_role() -> None:
    """Verify that future Python changes preserve complete documentation coverage."""

    repository_root = Path(__file__).resolve().parents[2]

    assert _undocumented_boundaries(repository_root) == ()


def test_declarative_files_start_with_a_plain_english_explanation() -> None:
    """Verify that non-code configuration and templates explain their purpose."""

    repository_root = Path(__file__).resolve().parents[2]

    for relative, comment_prefix in COMMENTED_DECLARATIVE_FILES.items():
        contents = (repository_root / relative).read_text(encoding="utf-8")
        assert _is_plain_english_explanation(
            _leading_comment(contents, comment_prefix)
        ), relative
