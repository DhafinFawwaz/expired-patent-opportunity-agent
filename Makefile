.DEFAULT_GOAL := help
.PHONY: help install lint format type test check demo run

help:  ## list targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install:  ## install the workspace
	uv sync

lint:  ## ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

format:  ## apply ruff formatting
	uv run ruff format .
	uv run ruff check --fix .

type:  ## mypy strict
	uv run mypy

test:  ## offline test suite
	uv run pytest -q

check: lint type test  ## everything CI runs

demo:  ## synthetic fixtures through the full pipeline, offline
	uv run patentic demo

run:  ## live run on the demo request
	uv run patentic run --request-file fixtures/requests/demo-cleaning-tools.yaml
