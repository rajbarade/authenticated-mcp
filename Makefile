.PHONY: check
check:
	uv sync --locked
	uv run --locked ruff check app tests
	uv run --locked ruff format --check app tests
	uv run --locked mypy app
	uv run --locked pytest -q
