# ADR-003: One adapter contract, keyed sources behind it

Status: accepted, 2026-11-07

## Context

The best status data (the USPTO maintenance fee events file) needs an Open Data Portal key, and the key needs ID.me identity verification, which the author did not do. The Official Gazette publishes the same expirations and reinstatements weekly with no login. EPO OPS gives INPADOC legal events after a free registration that was still pending during the build.

## Decision

Every source returns `EvidenceRecord`s with a URL, retrieval time, raw snippet, grade and synthetic flag. Official Gazette pages are the primary status source; BigQuery PatentsView tables give bibliographic data and claims; OPS is a cross-check that switches on when credentials exist; the ODP maintenance fee file has a tested parser that only runs with a key. A failing source returns an outage record instead of raising.

## Consequences

Fixtures, cassettes and live sources are interchangeable in tests and in the demo. Without OPS, status rests on one official source and confidence stops at `high`. The keyed parser ships unused, documented as such.

Confirmed by: `tests/adapters/test_http.py`, `tests/adapters/test_odp_maintfee.py`, `tests/graph/test_discovery_verify.py`.
