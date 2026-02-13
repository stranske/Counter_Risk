.PHONY: lint format format-check test

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

format-check:
	ruff format --check src/ tests/

test:
	pytest -m "not slow"

