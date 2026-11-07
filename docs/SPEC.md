# Specification

What patentic must do, written as EARS requirements. Each line names the test that checks it. The brief it comes from is in `case-study/case-study.md`.

## Scope

- THE SYSTEM SHALL research US patents only and SHALL NOT state anything about other jurisdictions. [T-16-1]
- THE SYSTEM SHALL label every report, deck and generated summary with "Research screening only. Not a legal opinion or freedom-to-operate determination." [T-21-2, T-22-2]
- WHEN fewer than the requested number of candidates survive screening THE SYSTEM SHALL report fewer and give the counts at each cut. [T-20-1]
- THE SYSTEM SHALL NOT invent candidates, numbers, quotes or sources. [T-15-3, T-23-1]

## Workflow

- WHEN a research request is submitted THE SYSTEM SHALL capture the technology category, intended product, jurisdiction and commercial constraints. [T-16-1]
- WHEN a plan is drafted THE SYSTEM SHALL pause for the user to approve, revise or abort it. [T-16-1, T-16-3]
- WHEN the user asks for a revision THE SYSTEM SHALL redraft the plan with the feedback, up to three times. [T-16-3, T-16-4]
- WHEN a resume value does not match the expected decision schema THE SYSTEM SHALL reject it, save nothing, and ask again. [T-16-5]
- WHEN candidates are scored THE SYSTEM SHALL pause for the user to keep, drop or flag candidates and confirm a shortlist of at most two. [T-18-5, T-18-6]
- WHILE a run is executing THE SYSTEM SHALL show stage progress in the terminal and write a redacted event log. [T-19-1, T-19-4]
- WHEN a run is interrupted THE SYSTEM SHALL resume from its last checkpoint with the same thread id. [T-19-5]

## Evidence and status

- WHEN a candidate appears in an Official Gazette expiration notice THE SYSTEM SHALL record the row as dated evidence with its source URL. [T-11-1]
- WHEN a candidate appears in an expiration notice AND a later reinstatement notice THE SYSTEM SHALL set status `reinstated` and attach both notices. [T-06-3]
- WHEN sources disagree AND a later official notice exists THE SYSTEM SHALL follow the later official notice and keep the other evidence visible. [T-06-7]
- WHEN sources disagree AND no later official notice resolves it THE SYSTEM SHALL set status `conflicting`. [T-06-6]
- WHEN the reinstatement scan does not cover every Gazette week published after the expiry date THE SYSTEM SHALL cap confidence at `medium` and state the gap. [T-07-2]
- THE SYSTEM SHALL compute confidence from rules over the evidence and SHALL NOT take it from a model. [T-07-1]
- WHEN a patent is a design or plant patent THE SYSTEM SHALL mark it `not_subject_to_maintenance_fees`. [T-06-1]
- WHEN today falls on or before the 4th, 8th or 12th grant anniversary with the fee unpaid THE SYSTEM SHALL mark the patent `in_grace_period`. [T-06-4]
- WHEN no maintenance events exist AND twenty years from filing have passed THE SYSTEM SHALL mark the patent `expired_end_of_term` and say patent term adjustment is unknown. [T-06-8]
- WHEN a source fails THE SYSTEM SHALL record an outage evidence item and continue with the other sources. [T-10-5, T-17-6]

## Screening and ranking

- WHEN a patent carries a powered co-classification THE SYSTEM SHALL exclude it. [T-09-2]
- WHEN a power term is an element of an independent claim THE SYSTEM SHALL exclude it, except hand or manual pumps and trigger sprayers. [T-09-3, T-09-4]
- THE SYSTEM SHALL rank candidates on commercial relevance, engineering effort, evidence quality and unresolved risk with weights shown in the report. [T-09-9]
- THE SYSTEM SHALL list related records (family, continuations, citations, same assignee, reissues, terminal disclaimers) with a status-to-verify flag. [T-09-7, T-09-8]

## Deliverables

- THE SYSTEM SHALL produce an editable .docx with the ten sections the brief lists, in order. [T-21-1]
- THE SYSTEM SHALL produce an editable .pptx of 8 to 10 slides covering the nine topics the brief lists. [T-22-1]
- THE SYSTEM SHALL generate both files from one validated dataset and SHALL fail validation when identifiers, statuses, scores or recommendations differ between them. [T-23-1, T-23-2]
- THE SYSTEM SHALL keep synthetic fixtures apart from real results, under the heading SYNTHETIC FIXTURE. [T-21-4]
