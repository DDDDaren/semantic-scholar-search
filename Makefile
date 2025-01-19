.PHONY: help check format lint type-check test clean

help:
	@echo "Available commands:"
	@echo "  make check      - Run all checks (format, lint, type-check, test)"
	@echo "  make format     - Run black formatter"
	@echo "  make lint       - Run flake8 linter"
	@echo "  make type-check - Run mypy type checker"
	@echo "  make test       - Run pytest with coverage"
	@echo "  make clean      - Remove Python cache files"

check: format lint type-check test

format:
	@echo "Running Black formatter..."
	poetry run black semantic_scholar_search

lint:
	@echo "Running Flake8 linter..."
	poetry run ruff check --fix semantic_scholar_search

type-check:
	@echo "Running MyPy type checker..."
	poetry run mypy semantic_scholar_search

test:
	@echo "Running tests with coverage..."
	poetry run mypy semantic_scholar_search
	poetry run pytest --cov=semantic_scholar_search --cov-report=term-missing
	poetry run black semantic_scholar_search
	poetry run ruff check --fix semantic_scholar_search

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 