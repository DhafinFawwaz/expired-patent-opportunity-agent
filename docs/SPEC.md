# Specification

What patentic must do, written as EARS requirements. Each line names the test that checks it. The brief it comes from is in `case-study/case-study.md`.

## Scope

- THE SYSTEM SHALL research US patents only and SHALL NOT state anything about other jurisdictions. (`tests/unit/test_identifiers.py::test_bad_patent_numbers_raise`)
- THE SYSTEM SHALL label every report, deck and generated summary with "Research screening only. Not a legal opinion or freedom-to-operate determination." (`tests/report/test_docx.py::test_label_in_header_title_and_section_ten`, `tests/report/test_pptx.py::test_label_on_title_last_and_every_content_slide_footer`)
- WHEN fewer than the requested number of candidates survive screening THE SYSTEM SHALL report fewer and give the counts at each cut. (`tests/graph/test_discovery_verify.py::test_rank_pool_limits_to_configured_size`, `tests/report/test_bundle.py::test_bundle_node_writes_json_and_prose_keys`)
- THE SYSTEM SHALL NOT invent candidates, numbers, quotes or sources. (`tests/llm/test_calls.py::test_technical_rejects_quote_not_in_text_then_falls_back`, `tests/report/test_bundle.py::test_every_cited_evidence_id_has_a_reference`)

## Workflow

- WHEN a research request is submitted THE SYSTEM SHALL capture the technology category, intended product, jurisdiction and commercial constraints. (`tests/graph/test_plan_approval.py::test_stream_stops_at_approval_interrupt`)
- WHEN a plan is drafted THE SYSTEM SHALL pause for the user to approve, revise or abort it. (`tests/graph/test_plan_approval.py::test_resume_approve_moves_to_discover`, `tests/graph/test_plan_approval.py::test_abort_ends_run`)
- WHEN the user asks for a revision THE SYSTEM SHALL redraft the plan with the feedback, up to three times. (`tests/graph/test_plan_approval.py::test_resume_revise_replans_with_feedback`, `tests/graph/test_plan_approval.py::test_revision_cap_forces_decision`)
- WHEN a resume value does not match the expected decision schema THE SYSTEM SHALL reject it, save nothing, and ask again. (`tests/graph/test_plan_approval.py::test_invalid_resume_is_rejected_and_reaskable`)
- WHEN candidates are scored THE SYSTEM SHALL pause for the user to keep, drop or flag candidates and confirm a shortlist of at most two. (`tests/graph/test_analysis_review.py::test_review_interrupt_payload_lists_candidates_and_not_analysed_count`, `tests/graph/test_analysis_review.py::test_review_shortlist_limit`)
- WHILE a run is executing THE SYSTEM SHALL show stage progress in the terminal and write a redacted event log. (`tests/cli/test_cli.py::test_events_log_writes_redacted_lines`, `tests/cli/test_cli.py::test_redact_hides_secrets_and_long_snippets`)
- WHEN a run is interrupted THE SYSTEM SHALL resume from its last checkpoint with the same thread id. (`tests/cli/test_resume_subprocess.py::test_run_stopped_at_review_resumes_in_a_new_process`)

## Evidence and status

- WHEN a candidate appears in an Official Gazette expiration notice THE SYSTEM SHALL record the row as dated evidence with its source URL. (`tests/adapters/test_og_notices.py::test_rows_carry_evidence_with_grade_a`)
- WHEN a candidate appears in an expiration notice AND a later reinstatement notice THE SYSTEM SHALL set status `reinstated` and attach both notices. (`tests/unit/test_status_rules.py::test_reinstated_after_lapse`)
- WHEN sources disagree AND a later official notice exists THE SYSTEM SHALL follow the later official notice and keep the other evidence visible. (`tests/unit/test_status_rules.py::test_later_official_notice_wins`, `tests/unit/test_status_rules.py::test_reinstatement_granted_before_the_lapse_notice_still_wins`)
- WHEN sources disagree AND no later official notice resolves it THE SYSTEM SHALL set status `conflicting`. (`tests/unit/test_status_rules.py::test_conflicting_without_resolving_notice`)
- WHEN the reinstatement scan does not cover every Gazette week published after the expiry date THE SYSTEM SHALL cap confidence at `medium` and state the gap. (`tests/unit/test_confidence.py::test_incomplete_scan_caps_at_medium`, `tests/unit/test_confidence.py::test_missing_week_after_expiry_breaks_coverage`)
- THE SYSTEM SHALL compute confidence from rules over the evidence and SHALL NOT take it from a model. (`tests/unit/test_confidence.py::test_assess_status_fills_confidence`)
- WHEN a patent is a design or plant patent THE SYSTEM SHALL mark it `not_subject_to_maintenance_fees`. (`tests/unit/test_status_rules.py::test_design_patent_not_subject`)
- WHEN today falls on or before the 4th, 8th or 12th grant anniversary with the fee unpaid THE SYSTEM SHALL mark the patent `in_grace_period`. (`tests/unit/test_status_rules.py::test_grace_period_includes_anniversary_day`)
- WHEN no maintenance events exist AND twenty years from filing have passed THE SYSTEM SHALL mark the patent `expired_end_of_term` and say patent term adjustment is unknown. (`tests/unit/test_status_rules.py::test_expired_end_of_term`, `tests/unit/test_term.py::test_estimate_term_end_pta_unknown`)
- WHEN a source fails THE SYSTEM SHALL record an outage evidence item and continue with the other sources. (`tests/graph/test_discovery_verify.py::test_source_outage_recorded_and_run_continues`, `tests/cli/test_cli.py::test_run_non_interactive_with_simulated_outages`)

## Screening and ranking

- WHEN a patent carries a powered co-classification THE SYSTEM SHALL exclude it. (`tests/unit/test_screening.py::test_tier1_rejects_suction_cleaner`)
- WHEN a power term is an element of an independent claim THE SYSTEM SHALL exclude it, except hand or manual pumps and trigger sprayers. (`tests/unit/test_screening.py::test_tier2_motor_in_independent_claim`, `tests/unit/test_screening.py::test_tier2_hand_pump_allowed`)
- THE SYSTEM SHALL rank candidates on commercial relevance, engineering effort, evidence quality and unresolved risk with weights shown in the report. (`tests/unit/test_scoring.py::test_scores_total_weights`)
- THE SYSTEM SHALL list related records (family, continuations, citations, same assignee, reissues, terminal disclaimers) with a status-to-verify flag. (`tests/unit/test_related.py::test_related_continuation_child_flagged`, `tests/unit/test_related.py::test_citations_assignee_and_disclaimer`)

## Deliverables

- THE SYSTEM SHALL produce an editable .docx with the ten sections the brief lists, in order. (`tests/report/test_docx.py::test_docx_has_ten_sections_in_order`)
- THE SYSTEM SHALL produce an editable .pptx of 8 to 10 slides covering the nine topics the brief lists. (`tests/report/test_pptx.py::test_deck_has_nine_slides_and_titles`)
- THE SYSTEM SHALL generate both files from one validated dataset and SHALL fail validation when identifiers, statuses, scores or recommendations differ between them. (`tests/report/test_validate.py::test_validate_passes_on_consistent_files`, `tests/report/test_validate.py::test_validate_fails_when_pptx_score_differs`)
- THE SYSTEM SHALL keep synthetic fixtures apart from real results, under the heading SYNTHETIC FIXTURE. (`tests/report/test_docx.py::test_synthetic_table_separate_with_heading`)
