.DEFAULT_GOAL := help

PATENTIC := uv run patentic
REQUEST ?= fixtures/requests/demo-cleaning-tools.yaml
APPROVE := --decisions fixtures/decisions/approve-all.yaml
OUTAGE ?= og
ID ?= $(shell ls -t outputs/runs 2>/dev/null | head -1)

.PHONY: help install lint format type test test-live test-render check \
	demo demo-auto demo-no-llm run run-auto run-offline replay outage resume cost latest \
	schemas templates pack-replay video llm-keys llm-models llm-check clean clean-cache

help:  ## list targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

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

test-live:  ## tests that hit real sources (needs network and credentials)
	PATENTIC_LIVE=1 uv run pytest -q -m live

test-render:  ## tests that render with LibreOffice
	uv run pytest -q -m render

check: lint type test  ## everything CI runs

demo:  ## synthetic fixtures through the full pipeline, offline
	$(PATENTIC) demo

demo-auto:  ## demo with both gates approved from a script
	$(PATENTIC) demo $(APPROVE)

demo-no-llm:  ## demo with templates instead of a model
	$(PATENTIC) demo --no-llm $(APPROVE)

run:  ## live run (REQUEST=path to change the request)
	$(PATENTIC) run --request-file $(REQUEST)

run-auto:  ## live run with both gates approved from a script
	$(PATENTIC) run --request-file $(REQUEST) $(APPROVE)

run-offline:  ## run on cached data only
	$(PATENTIC) run --request-file $(REQUEST) --offline

replay:  ## rerun the committed real run offline, no keys needed
	$(PATENTIC) run --replay $(APPROVE)

outage:  ## live run with one source failing (OUTAGE=og|bigquery|ops)
	$(PATENTIC) run --request-file $(REQUEST) --simulate-outage $(OUTAGE) $(APPROVE)

resume:  ## continue a stopped run (ID=run id, default the newest)
	$(PATENTIC) resume $(ID)

cost:  ## cost record of a run (ID=run id, default the newest)
	$(PATENTIC) cost $(ID)

latest:  ## newest run and its files
	@echo outputs/runs/$(ID)
	@ls outputs/runs/$(ID)

schemas:  ## regenerate JSON Schemas in schemas/
	$(PATENTIC) schemas

templates:  ## regenerate the docx and pptx templates
	uv run python scripts/make_templates.py

pack-replay:  ## pack a finished live run into fixtures/replay (ID=run id)
	uv run python scripts/build_replay.py $(ID)

video:  ## record docs/demo/demo.mp4 (needs vhs)
	vhs docs/demo/demo.tape

llm-keys:  ## which free-LLM providers have keys, with signup steps
	uv run freellm keys --steps

llm-models:  ## ranked free models currently reachable
	uv run freellm models

llm-check:  ## send a real request to every free model, list the ones that answered
	uv run freellm ping --refresh --max-tokens 400
	uv run freellm models --available

clean:  ## remove Python and tool caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -path ./.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +

clean-cache:  ## delete .cache/ so the next live run fetches everything again
	rm -rf .cache
