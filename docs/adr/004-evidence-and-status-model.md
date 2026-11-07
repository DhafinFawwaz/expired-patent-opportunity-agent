# ADR-004: Dated evidence, rule-based status and confidence

Status: accepted, 2026-11-07

## Context

An expired patent can be reinstated months or years later. Secondary displays such as Google Patents lag behind the official notices. A status label without a date and a reinstatement check is not evidence.

## Decision

Events from every source map onto one vocabulary. Status comes from ordered rules: eligibility, end of term, revival after lapse, lapse with a complete reinstatement scan, pending petition, grace period, in force. A later official event beats an earlier or secondary one. Events are ordered by legal effect, not by publication: a lapse counts from its expiry date, because the Gazette prints it about eight weeks later, and a reinstatement counts from the date the petition was granted. Ordering by notice date would miss the one in five reinstatements that are granted before the expiry notice appears. Confidence is one of five words computed from the number of independent sources and whether the reinstatement scan covers every later Gazette week. Each evidence item carries an Admiralty grade.

## Consequences

The report can say why it believes a status and how sure it is, and the conflicting case (US 8,646,606: reinstated per the Gazette, expired per Google) comes out as `reinstated` with the lagging source shown. Patent term adjustment is not in any public table, so end-of-term dates always say it is unknown.

Confirmed by: `tests/unit/test_status_rules.py`, `tests/unit/test_confidence.py`.
