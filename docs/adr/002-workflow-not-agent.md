# ADR-002: A fixed workflow, not an autonomous agent

Status: accepted, 2026-11-07

## Context

The brief fixes eleven stages in order and accepts a single agent. The run must work on free models whose tool calling and JSON output are unreliable, and every claim in the report has to trace back to a source.

## Decision

patentic is a LangGraph `StateGraph` with a fixed path. Plain code makes every data call, applies the status rules, scores candidates, renders and validates the files. A model is used for four things only: drafting the plan, summarising each analysed patent, writing the opportunity rationale, and writing report paragraphs. Each call returns a small schema, cites evidence ids that code checks, and has a templated fallback.

## Consequences

The run is reproducible and testable without a model. A weak or rate-limited model degrades the prose, not the findings. The cost is that the agent cannot decide on its own to search somewhere new; changing the search means changing the plan or the code.

Confirmed by: `tests/graph/test_plan_approval.py`, `tests/llm/test_calls.py`.
