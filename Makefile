# OpenClaw — developer convenience targets
# Usage: make <target>

.PHONY: help install test doctor run verify clean lint

PYTHON  := python3
VENV    := .venv
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/pytest
CONFIG  := config.yaml

help:
	@echo "OpenClaw make targets:"
	@echo "  make install   — create venv and install all deps"
	@echo "  make test      — run unit test suite"
	@echo "  make doctor    — validate config without starting the agent"
	@echo "  make run       — start the agent (dev mode)"
	@echo "  make verify    — full smoke test: tests + live health check"
	@echo "  make clean     — remove venv, cache, egg-info"
	@echo "  make lint      — run ruff (if installed)"

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -e ".[dev]" --quiet
	@echo "✓ installed"

test:
	$(PYTEST) tests/ -v

doctor:
	$(VENV)/bin/python scripts/doctor.py $(CONFIG)

run:
	./scripts/run_local.sh $(CONFIG)

verify:
	./scripts/verify.sh

clean:
	rm -rf $(VENV) __pycache__ src/openclaw/__pycache__ src/openclaw.egg-info \
	       .pytest_cache .coverage htmlcov
	find . -name "*.pyc" -delete
	@echo "✓ cleaned"

lint:
	@$(VENV)/bin/ruff check src/ tests/ 2>/dev/null || \
	  echo "ruff not installed — run: pip install ruff"
