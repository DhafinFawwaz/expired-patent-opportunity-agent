# ADR-002: A fixed workflow, not an autonomous agent

Status: accepted, 2026-11-07

## Context

The brief fixes eleven stages in order and accepts a single agent. The run must work on free models whose tool calling and JSON output are unreliable, and every claim in the report has to trace back to a source.

## Decision

patentic is a LangGraph `StateGraph` with a fixed path. Plain code makes every data call, applies the status rules, scores candidates, renders and validates the files. A model is used for four things only: drafting the plan, summarising each analysed patent, writing the opportunity rationale, and writing report paragraphs. Each call returns a small schema, cites evidence ids that code checks, and has a templated fallback.

## Consequences

The run is reproducible and testable without a model. A weak or rate-limited model degrades the prose, not the findings. The cost is that the agent cannot decide on its own to search somewhere new; changing the search means changing the plan or the code.

## Amendment, 2026-11-11: the plan drives the search

Until this change, discovery searched a fixed CPC list and ignored the plan, so revising the plan at gate 1 changed nothing. Now the approved plan's CPC codes are added to the search, and before the gate the model gets up to two rounds to test its plan against BigQuery and revise it. Code still decides what the model may change: added codes must sit in the subclasses the default list already uses, powered co-classes are refused, the default list is always searched, and the plan's own power terms only flag a claim for review. A failed probe or a failed answer ends the loop and the run continues with the plan it has.

We considered a full tool-calling agent with the fixed workflow as a fallback and rejected it. A fallback catches errors, not an agent that quietly skips the reinstatement scan, and tool calling is where free models fail most.

Confirmed by: `tests/graph/test_plan_approval.py`, `tests/graph/test_plan_scope.py`, `tests/unit/test_search_scope.py`, `tests/llm/test_calls.py`.
