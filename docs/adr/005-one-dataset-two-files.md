# ADR-005: One validated dataset feeds both files

Status: accepted, 2026-11-07

## Context

The brief requires the Word report and the deck to agree on identifiers, statuses, scores and recommendations.

## Decision

A frozen Pydantic `ReportBundle` is built once and validated. Both renderers read only from it through shared formatters. After rendering, the validator reopens both files, extracts the candidate facts and compares them with the bundle and with each other.

## Consequences

A mismatch fails the run instead of shipping. Layout changes are cheap because content lives in the bundle. The cost is that hand edits to one file are not reflected in the other, which is acceptable for generated deliverables.

Confirmed by: `tests/report/test_validate.py`.
