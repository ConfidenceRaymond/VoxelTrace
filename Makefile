VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
HACK   := $(abspath ..)
export PIP_CACHE_DIR := $(HACK)/tmp/pip-cache

.PHONY: help venv install test lint format app env-snapshot audit

help:
	@echo "targets: venv install test lint format app env-snapshot audit"

venv:
	test -d $(VENV) || python3 -m venv $(VENV)

install: venv
	$(PIP) install -e ".[app,dev]"

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .

format:
	$(VENV)/bin/ruff format .

app:
	scripts/run_app.sh

env-snapshot:
	scripts/check_environment.sh > docs/environment_snapshot.md

audit:
	scripts/cleanup_audit.sh
