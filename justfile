# Nelson CLI Development Commands

# Show available commands
default:
    @just --list

# Install the package in development mode with dev dependencies
install:
    uv pip install -e ".[dev]"

# Run all tests with coverage
test:
    pytest

# Run tests without coverage report
test-fast:
    pytest --no-cov

# Run tests in watch mode (requires pytest-watch)
test-watch:
    pytest-watch

# Run type checking with mypy
typecheck:
    mypy src/nelson tests

# Run linter (check only, no fixes)
lint:
    ruff check src tests

# Run linter and fix issues automatically
lint-fix:
    ruff check --fix src tests

# Format code with ruff
format:
    ruff format src tests

# Run all quality checks (lint, typecheck, test)
check: lint typecheck test

# Clean build artifacts and caches
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache
    rm -rf dist build *.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Build the package
build:
    uv build

# Run the CLI (example: just run --help)
run *ARGS:
    nelson {{ARGS}}

# Show nelson version
version:
    nelson --version
