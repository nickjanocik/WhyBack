.DEFAULT_GOAL := help

.PHONY: help sync format lint type test quality

help:
	@echo "WhyBack developer commands"
	@echo "  make sync     Install the locked development environment"
	@echo "  make format   Format source and tests"
	@echo "  make lint     Check formatting and lint rules"
	@echo "  make type     Run Pyright"
	@echo "  make test     Run deterministic tests"
	@echo "  make quality  Run the auditable quality gate"

sync:
	uv sync --frozen --all-extras

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

type:
	uv run pyright

test:
	uv run pytest

quality:
	uv run python scripts/run_quality_gate.py
