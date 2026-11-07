# Case study docs: index

Markdown conversion of `case-study.pdf` (repo root), the 4 pages it links to, and the useful pages those link to (crawled up to depth 3). Read this before starting research or design work.

## Files

| File | What it is | Fidelity |
|---|---|---|
| [case-study.md](case-study.md) | The assignment brief | Verbatim. Word-level diff against the PDF text: 863/863 words match. |
| [references/01-uspto-maintain-your-patent.md](references/01-uspto-maintain-your-patent.md) | USPTO "Maintain your patent": fee windows, grace periods, Storefront, Official Gazette, reinstatement | Full page body. Summary at top. |
| [references/02-uspto-petition-delayed-maintenance-fee.md](references/02-uspto-petition-delayed-maintenance-fee.md) | USPTO petition page: reinstatement via 37 CFR 1.378(b) | Full page body. Summary at top. |
| [references/03-uspto-managing-a-patent.md](references/03-uspto-managing-a-patent.md) | USPTO "Managing a patent": right to exclude, term, PTA/PTE, infringement | Full page body. Summary at top. |
| [references/04-mpep-301-ownership-assignability.md](references/04-mpep-301-ownership-assignability.md) | MPEP §301 / §301.01: ownership, assignment, licensing, assignment records | Full sections. Summary at top. |

**Followed sublinks (depth 2–3).** [crawl-log.md](crawl-log.md) has the link tree and lists every skipped or failed link with its reason.

| File | What it is | Depth, from |
|---|---|---|
| [references/05-federal-register-91fr37826-unintentional-delay-rule.md](references/05-federal-register-91fr37826-unintentional-delay-rule.md) | Final rule: reinstatement threshold changed from 2 years to **1 year** (effective 2026-08-13) | 2, from 02 |
| [references/06-mpep-2500-maintenance-fees.md](references/06-mpep-2500-maintenance-fees.md) | MPEP §§2501–2591: exact expiry date, notices, status lookups, reinstatement, **intervening rights** | 2, from 01/02 |
| [references/07-statutes-35usc-41-154-253.md](references/07-statutes-35usc-41-154-253.md) | Statutes: maintenance fees, patent term and PTA, disclaimers | 2, from 02/03 |
| [references/08-rules-37cfr-1362-1366-1378.md](references/08-rules-37cfr-1362-1366-1378.md) | Rules: fee timing, payment validity, reinstatement petition | 2, from 01–03 |
| [references/09-uspto-patent-term-calculator.md](references/09-uspto-patent-term-calculator.md) | Factors for computing the end-of-term date | 2, from 01/03 |
| [references/10-uspto-quick-guide-locating-patent-term-info.md](references/10-uspto-quick-guide-locating-patent-term-info.md) | Where each term factor lives; terminal-disclaimer check (describes retired systems) | 3, from 09 |
| [references/11-uspto-official-gazette.md](references/11-uspto-official-gazette.md) | Official Gazette: weekly publication, 52-issue online window, bulk data | 1–2, from 01 |
| [references/12-og-weekly-notices-sample-2026-11-03.md](references/12-og-weekly-notices-sample-2026-11-03.md) | **Real expiration and reinstatement lists**: format, parsing notes, sample rows | 3, from 11 |
| [references/13-uspto-assignments-change-search-ownership.md](references/13-uspto-assignments-change-search-ownership.md) | Ownership lookup (Patent Assignment Search) | 2, from 03 |
| [references/14-uspto-reissue-maintenance-fee-faq.md](references/14-uspto-reissue-maintenance-fee-faq.md) | Reissue families: each reissue maintained separately since 2018 | 2, from 01 |

In each reference file, the "Key facts for the expired-patent agent" section is a summary written for this project. Everything under "Full page content" is source text. All pages were retrieved on 2026-11-07.

**Reading order:** `case-study.md`, then the checklist below, then the references as needed.

## Requirements at a glance

This is a condensed checklist. `case-study.md` is authoritative.

**Ground rules**
- US-only. Do not infer worldwide availability.
- Never invent candidates. Return fewer than five if evidence is thin, and explain why.
- Output is research screening only, never legal clearance or FTO. The report must carry the label: *"Research screening only. Not a legal opinion or freedom-to-operate determination."*
- Synthetic fixtures must be clearly separated from real results.
- The workflow must actually execute tools. An LLM writing a report is not enough.
- Single agent is fine. Multiple agents need an engineering justification.

**Demo scenario:** up to 5 non-powered household cleaning tool patents that appear expired for nonpayment of maintenance fees. Recommend up to 2 for technical and legal review.

**Pipeline stages (11):** Intake → Plan → Approval (user can approve or revise) → Discovery → Normalisation → Status verification (evidence timeline) → Technical analysis → Opportunity screening → Human review → Generation → Validation.

**Synthetic fixtures (6):** expired for nonpayment · expired then reinstated · inside grace period · expired at end of term · conflicting/incomplete evidence · has a related active patent.

**Deliverables**
1. CLI or light web app: submit request, approve/revise plan, see progress, review candidates and evidence, generate files.
2. `.docx` report, 6–10 pages excluding references, 10 required sections.
3. `.pptx` deck, 8–10 slides, 9 required topics.
4. GitHub repo shared with `neiltan1688888888`, containing: README, `.env.example`, manifest and lockfile, `src/ tests/ fixtures/ schemas/ docs/ outputs/`, architecture diagram, data-source docs, tests, sample outputs, sanitised logs, limitations, time spent, run cost.

Report and deck must come from the same validated data. IDs, statuses, scores, and recommendations must match across both.

**Timebox:** 8–12 h, due within 5 calendar days. A 20-min demo (5 architecture / 10 live / 5 tests and failures) must show a reinstated fixture, a conflicting-status case, and a **source outage**.

**AI assistants** are allowed. Disclose their use.

## Domain rules from the references

These matter for status logic:

| Rule | Source |
|---|---|
| Maintenance fees apply only to **utility and reissue utility** patents filed on or after 1980-12-12. Design and plant patents never "expire for nonpayment". | 01, 03 |
| Fee windows from issue date: 3–3.5 / 7–7.5 / 11–11.5 yrs. Surcharge grace: 3.5–4 / 7.5–8 / 11.5–12 yrs. | 01 |
| Unpaid by end of the grace period (year 4 / 8 / 12) means the patent expires on the day the grace period ends. | 01, 03 |
| Weekend or federal-holiday deadlines roll to the next business day. | 01 |
| **Exact expiry date:** the end of the 4th, 8th or 12th anniversary of grant. A weekend or holiday extends the payment day, not the expiry date. | 06, 08 |
| Expiry for nonpayment is reversible: petition under 37 CFR 1.378(b), possible at any later time. Once accepted, the patent "shall be considered as not having expired". ePetitions are granted instantly. | 01, 02, 06 |
| Reinstatement petitions filed after 2026-08-13 need additional information and the higher fee once **more than 1 year** has passed since expiry (previously 2 years). | 05 |
| **Intervening rights:** anyone who used or prepared to use the invention between the end of the grace period and the reinstatement may be allowed by a court to continue. | 06, 07 |
| A short or invalid payment doesn't count, so a patent can expire despite a payment attempt (a source of conflicting evidence). | 06, 08 |
| Since 2018-01-16, each reissue patent in a family needs its own fee, and the schedule follows the original grant date. | 06, 14 |
| A terminal disclaimer caps a patent's term at the related patent's expiry. Check it in the front-page "Notice" field. | 07, 10 |
| Term is generally 20 yrs from the earliest US non-provisional filing (35 U.S.C. 120/121/365(c)), plus PTA/PTE. USPTO does not compute expiry dates. | 01, 03 |
| Expiry gives no right to practise if other unexpired patents cover the product. Other law (FDA, injunctions, national security) may also block. | 03, 04 |

**Status evidence sources named in the references**
- Patent Maintenance Fees Storefront: <https://fees.uspto.gov/MaintenanceFees>. **Requires a USPTO.gov login.** Payment statements only from 2009-10-01.
- **Official Gazette weekly notices** (`https://patentsgazette.uspto.gov/weekNN/OG/TOC.htm`): both "Notice of Expiration … Failure to Pay Maintenance Fee" and "Patents Reinstated Due to the Acceptance of a Late Maintenance Fee". Public, no login. Only the last 52 weeks are online, and listings appear about 8 weeks after expiry. Rows have patent number, application number and dates only, with no titles. Format and parsing notes are in 12.
- OG bulk archive since 2002 (Open Data Portal dataset `gzlst`). Its API returned 401 without a key.
- Patent Assignment Search, for ownership and related-patent owners: <https://assignmentcenter.uspto.gov/search/patent>

None of the linked pages document a programmatic patent-data API (e.g. Open Data Portal APIs or PatentsView) beyond the gzlst dataset. Data access (including whether an API key is needed) still has to be researched and documented.

## Known gaps and discrepancies

- **Reinstatement threshold: resolved.** References 01 and 06 (MPEP) still say 2 years. The final rule in 05 changed it to **1 year** for petitions filed from 2026-08-13. Use 1 year for current petitions and 2 years for petitions filed before then.
- Reference 10 describes retired USPTO systems (Public PAIR, PatFT). Use Patent Center and Patent Public Search instead.
- **Case-study numbering:** the PDF jumps 4 → 6 → 9. Sections 5, 7, and 8 don't exist in the source. Nothing was lost in conversion.
- The **"supplied video script"** mentioned in §1 is not in this repo and is not linked from the PDF.
- Citation 4 (MPEP §301) is about ownership and assignment. The case study uses it only for the "other legal or regulatory requirements" point (§301 I).
