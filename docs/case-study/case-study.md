---
title: "Software Engineer Case Study: AI Agent for Expired-Patent Opportunity Intelligence"
source_file: case-study.pdf (repo root)
source_author: AIHK Team (PDF metadata)
source_created: 2026-11-06 (PDF metadata, WIB)
source_pages: 4
converted: 2026-11-07
fidelity: Verbatim. Wording, punctuation, list order, and section numbering are exactly as in the PDF. Only formatting (Markdown headings, tables, lists) and link targets were added.
---

# Software Engineer Case Study: AI Agent for Expired-Patent Opportunity Intelligence

> **Conversion notes (not part of the original text)**
> - The PDF's section numbers are **1, 2, 3, 4, 6, 9**. Sections 5, 7, and 8 do not exist in the source. They were not dropped during conversion.
> - Each `[uspto]` marker in the PDF is a hyperlink. They are resolved below as `[uspto][n]`, with targets listed in [Citation links](#citation-links). Full extracted text of each linked page is in [`references/`](references/).
> - Page breaks in the PDF: page 2 starts at "A patent still within its maintenance-fee grace period"; page 3 starts at "10. Limitations, assumptions, and references"; page 4 starts at "Be prepared to demonstrate a reinstated-patent fixture".

## 1. Business context

Build an AI agent that discovers potentially expired US patents, verifies available status evidence, and produces commercially useful opportunity assessments for product teams, manufacturers, and technology researchers.

The goal is **evidence-backed** opportunity discovery—not a system that labels expired patents “free technology” or automatically recommends copying a product.

The supplied video script is an idea source, not verified research. Your implementation must account for these important distinctions:

- US utility-patent maintenance fees are generally due at 3½, 7½, and 11½ years after grant, with six-month surcharge grace periods—not simply at years 3, 7, and 11.[[uspto][1]]
- A patent that expires for nonpayment may subsequently be reinstated through acceptance of delayed maintenance-fee payment. Historical expiry alone is therefore insufficient evidence of current status.[[uspto][2]]
- Expiry of one patent does not establish freedom to manufacture or sell a product: other unexpired patents may still cover the proposed activity. Other legal or regulatory requirements may also apply.[[uspto][3]][[uspto][4]]

Your system should identify candidates for further investigation, explain uncertainty, and prepare a review package—not issue legal clearance.

## 2. Your assignment

Design and implement an AI agent that can:

1. Accept a technology category and commercial research brief.
2. Discover relevant US patent records.
3. Retrieve available patent and maintenance-status evidence.
4. Distinguish apparent nonpayment expiry from other statuses.
5. Check for subsequent reinstatement evidence.
6. Summarise relevant claims and technical disclosures.
7. Identify related patent records requiring further review.
8. Rank potential commercial opportunities.
9. Generate a Word report and PowerPoint presentation.
10. Deliver the application, documentation, tests, and sample outputs through GitHub.

A single-agent architecture is acceptable. Multiple agents are optional and must have a clear engineering justification.

## 3. Demonstration scenario

Use the following research request:

> “Identify up to five US patent opportunities relating to non-powered household cleaning tools that appear to have expired for nonpayment of maintenance fees. Assess the disclosed technology, available status evidence, potential commercial applications, implementation challenges, and unresolved patent risks. Recommend up to two candidates for further technical and legal review.”

Keep the assessment limited to US patent research. Do not infer worldwide availability.

If fewer than five candidates can be supported by the available evidence, return fewer and explain the coverage limitation. Do not invent candidates to meet the target.

For reproducible testing, also create synthetic fixtures representing:

- A patent apparently expired for nonpayment.
- A patent expired for nonpayment and subsequently reinstated.
- A patent still within its maintenance-fee grace period.
- A patent expired at the end of its term.
- A record with conflicting or incomplete status evidence.
- A candidate with a related active patent requiring review.

Clearly distinguish synthetic fixtures from real research results.

## 4. Required agent workflow

| Stage | Required behaviour |
|---|---|
| Intake | Capture technology category, intended product, jurisdiction, and commercial constraints. |
| Plan | Propose search terms, sources, screening criteria, and output structure. |
| Approval | Allow the user to approve or revise the research plan. |
| Discovery | Retrieve candidate patents through documented, permitted data-access methods. |
| Normalisation | Validate identifiers, dates, source records, and patent relationships. |
| Status verification | Construct an evidence timeline covering maintenance events, expiry indicators, and reinstatement evidence. |
| Technical analysis | Summarise relevant claims, disclosed mechanisms, and implementation unknowns. |
| Opportunity screening | Compare commercial relevance, engineering effort, evidence quality, and unresolved risks. |
| Human review | Present shortlisted candidates and reasons for inclusion or exclusion. |
| Generation | Produce coordinated Word and PowerPoint deliverables. |
| Validation | Check citations, identifiers, calculations, status labels, and consistency. |

The workflow must demonstrate actual tool execution. A chatbot that merely writes a patent-market report is insufficient.

## 6. Required deliverables

### Deliverable 1: Working application

Provide a command-line or lightweight web interface supporting:

- Research-request submission.
- Plan approval or revision.
- Execution-progress visibility.
- Candidate and evidence review.
- Word and PowerPoint generation.

### Deliverable 2: Word report

Generate an editable .docx report of approximately 6–10 pages, excluding references, containing:

1. Executive summary.
2. Search scope and methodology.
3. Candidate comparison table.
4. Patent-status evidence timelines.
5. Technical and claims summaries.
6. Related-patent findings.
7. Commercial opportunity assessment.
8. Recommended shortlist and rationale.
9. Engineering validation and specialist-review next steps.
10. Limitations, assumptions, and references.

Include the label:

> Research screening only. Not a legal opinion or freedom-to-operate determination.

### Deliverable 3: PowerPoint presentation

Generate an editable .pptx presentation of 8–10 slides covering:

- Business objective.
- Agent workflow and architecture.
- Search scope and evidence sources.
- Candidate comparison.
- Status-verification example.
- Technical opportunity.
- Commercial assessment.
- Unresolved risks.
- Recommended next steps.

Generate both deliverables from the same validated research data. Patent identifiers, statuses, scores, and recommendations must agree across files.

### Deliverable 4: GitHub repository

Submit the repository for review by GitHub account neiltan1688888888.

Suggested structure:

```text
README.md
.env.example
<dependency manifest and lockfile>
src/
tests/
fixtures/
schemas/
docs/
outputs/
```

Include:

- Complete source code.
- Reproducible setup and execution instructions.
- Architecture diagram and design rationale.
- Data-source and access-method documentation.
- Synthetic test fixtures.
- Automated tests.
- Sample Word and PowerPoint outputs.
- Sanitised execution logs.
- Known limitations.
- Actual time spent and approximate sample-run cost.

## 9. Timebox and demonstration

Suggested timebox: 8–12 hours, submitted within five calendar days. Prioritise one complete vertical workflow over broad patent coverage.

Prepare a 20-minute walkthrough:

- 5 minutes: architecture and technical decisions.
- 10 minutes: live workflow and generated deliverables.
- 5 minutes: tests, failure handling, and production improvements.

Be prepared to demonstrate a reinstated-patent fixture, a conflicting-status case, and a source outage.

AI coding assistants are permitted. Disclose their use and be able to explain, test, and modify the submitted implementation.

---

## Citation links

The four `[uspto]` hyperlinks in the PDF, in document order:

| # | Supports the claim | URL | Extracted copy |
|---|---|---|---|
| 1 | Maintenance fees due at 3½ / 7½ / 11½ years, with 6-month surcharge grace periods | https://www.uspto.gov/patents/maintain | [references/01-uspto-maintain-your-patent.md](references/01-uspto-maintain-your-patent.md) |
| 2 | Patents expired for nonpayment can be reinstated by accepting delayed payment | https://www.uspto.gov/patents/apply/petitions/19-acceptance-delayed-payment-maintenance-fee-after-expiration | [references/02-uspto-petition-delayed-maintenance-fee.md](references/02-uspto-petition-delayed-maintenance-fee.md) |
| 3 | Expiry doesn't give freedom to operate: other unexpired patents may cover the activity | https://www.uspto.gov/patents/basics/manage | [references/03-uspto-managing-a-patent.md](references/03-uspto-managing-a-patent.md) |
| 4 | Other legal or regulatory requirements may also apply | https://www.uspto.gov/web/offices/pac/mpep/s301.html | [references/04-mpep-301-ownership-assignability.md](references/04-mpep-301-ownership-assignability.md) |

[1]: https://www.uspto.gov/patents/maintain
[2]: https://www.uspto.gov/patents/apply/petitions/19-acceptance-delayed-payment-maintenance-fee-after-expiration
[3]: https://www.uspto.gov/patents/basics/manage
[4]: https://www.uspto.gov/web/offices/pac/mpep/s301.html
