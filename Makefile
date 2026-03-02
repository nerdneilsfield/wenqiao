.PHONY: test lint format typecheck check fix

test:
	uv run pytest -v --tb=short

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/md_mid/

check: lint typecheck test

fix:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/
