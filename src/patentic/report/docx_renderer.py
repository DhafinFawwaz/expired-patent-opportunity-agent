from collections.abc import Sequence
from pathlib import Path
from typing import Final

from docx import Document
from docx.document import Document as DocxDocument
from docx.shared import Pt
from docx.table import Table

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.formatters import (
    fmt_confidence,
    fmt_date,
    fmt_score,
    fmt_source,
    fmt_status,
)
from patentic.report.oxml import add_hyperlink, repeat_header_row, shade_header_row

SECTIONS: Final[tuple[str, ...]] = (
    "Executive summary",
    "Search scope and methodology",
    "Candidate comparison",
    "Patent-status evidence timelines",
    "Technical and claims summaries",
    "Related-patent findings",
    "Commercial opportunity assessment",
    "Recommended shortlist and rationale",
    "Engineering validation and specialist-review next steps",
    "Limitations, assumptions and references",
)
_PAGE_BREAK_BEFORE: Final[frozenset[int]] = frozenset({3, 5, 7, 10})
COMPARISON_HEADER: Final[tuple[str, ...]] = (
    "Patent",
    "Title",
    "Status",
    "Confidence",
    "Score",
    "Recommendation",
)


def render_docx(bundle: ReportBundle, template: Path, out: Path) -> Path:
    doc: DocxDocument = Document(str(template))
    doc.core_properties.title = f"Expired-patent screening: {bundle.request.technology_category}"
    doc.core_properties.subject = LABEL
    doc.core_properties.author = "patentic"
    header = doc.sections[0].header.paragraphs[0]
    header.text = f"{LABEL}  Run {bundle.run.thread_id}"
    doc.add_heading(f"Expired-patent screening: {bundle.request.technology_category}", level=0)
    doc.add_paragraph(
        f"Run {bundle.run.thread_id}, {bundle.run.created:%Y-%m-%d}. US patents only."
    )
    doc.add_paragraph(LABEL, style="Disclaimer")
    writers = (
        _executive,
        _methodology,
        _comparison,
        _timelines,
        _technical,
        _related,
        _commercial,
        _shortlist,
        _next_steps,
        _limitations,
    )
    for number, (title, writer) in enumerate(zip(SECTIONS, writers, strict=True), start=1):
        if number in _PAGE_BREAK_BEFORE:
            doc.add_page_break()  # type: ignore[no-untyped-call]
        doc.add_heading(f"{number}. {title}", level=1)
        writer(doc, bundle)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


def _table(doc: DocxDocument, header: Sequence[str], rows: Sequence[Sequence[str]]) -> Table:
    table: Table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, header, strict=True):
        cell.text = text
    for row in rows:
        cells = table.add_row().cells  # type: ignore[no-untyped-call]
        for cell, text in zip(cells, row, strict=True):
            cell.text = text
    shade_header_row(table)
    repeat_header_row(table)
    for row_cells in table.rows:
        for cell in row_cells.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
    return table


def _bullets(doc: DocxDocument, items: Sequence[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def _executive(doc: DocxDocument, bundle: ReportBundle) -> None:
    doc.add_paragraph(bundle.prose.get("executive_summary", ""))


def _methodology(doc: DocxDocument, bundle: ReportBundle) -> None:
    doc.add_paragraph(bundle.prose.get("methodology", ""))
    _bullets(doc, bundle.methodology)
    flow = bundle.flow
    doc.add_paragraph("How the candidate set narrowed:", style="Caption")
    _table(
        doc,
        ("Step", "Patents"),
        [
            ("Found in the cleaning-tool CPC groups", str(flow.found)),
            ("Listed as expired for nonpayment in the window", str(flow.expired_in_window)),
            ("Passed the non-powered screen", str(flow.passed_screening)),
            ("Status verified", str(flow.status_verified)),
            ("Analysed and scored", str(flow.analysed)),
            ("Eligible but not analysed (capacity)", str(flow.not_analysed)),
            ("Recommended for review", str(flow.recommended)),
        ],
    )
    plan = bundle.plan
    doc.add_paragraph(f"CPC prefixes searched: {', '.join(plan.cpc_codes) or 'n/a'}.")
    doc.add_paragraph(f"Sources: {'; '.join(plan.sources) or 'n/a'}.")


def _comparison_rows(candidates: Sequence[CandidateReport]) -> list[tuple[str, ...]]:
    return [
        (
            c.display,
            c.title,
            fmt_status(c.status.label),
            fmt_confidence(c.status.confidence),
            fmt_score(c.scores.total if c.scores else None),
            c.recommendation,
        )
        for c in candidates
    ]


def _comparison(doc: DocxDocument, bundle: ReportBundle) -> None:
    real: list[CandidateReport] = [c for c in bundle.candidates if not c.is_synthetic]
    synthetic: list[CandidateReport] = [c for c in bundle.candidates if c.is_synthetic]
    if not bundle.candidates:
        doc.add_paragraph("No candidate passed the evidence and screening checks.")
        return
    if real:
        _table(doc, COMPARISON_HEADER, _comparison_rows(real))
    if synthetic:
        doc.add_paragraph(
            "SYNTHETIC FIXTURE: made-up patents used to test the pipeline, not research results."
        )
        _table(doc, COMPARISON_HEADER, _comparison_rows(synthetic))


def _timeline(doc: DocxDocument, report: CandidateReport) -> None:
    status = report.status
    doc.add_heading(f"{report.display}: {report.title}", level=2)
    doc.add_paragraph(
        f"Status: {fmt_status(status.label)} as of {fmt_date(status.as_of)}, "
        f"confidence {fmt_confidence(status.confidence)}."
    )
    _table(
        doc,
        ("Date", "Event", "Source", "Grade"),
        [(fmt_date(r.date), r.event, fmt_source(r.source), r.grade) for r in report.timeline],
    )
    for note in status.notes:
        doc.add_paragraph(note, style="Disclaimer")


def _timelines(doc: DocxDocument, bundle: ReportBundle) -> None:
    for report in bundle.candidates:
        _timeline(doc, report)
    if bundle.illustration:
        doc.add_paragraph(f"Worked example. {bundle.illustration_note}")
        _timeline(doc, bundle.illustration)


def _technical(doc: DocxDocument, bundle: ReportBundle) -> None:
    for report in bundle.candidates:
        doc.add_heading(f"{report.display}: {report.title}", level=2)
        technical = report.technical
        if technical is None:
            doc.add_paragraph("Not summarised.")
            continue
        doc.add_paragraph(technical.summary)
        doc.add_paragraph(f"Mechanism: {technical.mechanism}")
        _bullets(doc, [f"Claim element: {e}" for e in technical.key_claim_elements])
        _bullets(doc, [f"Unknown: {u}" for u in technical.implementation_unknowns])


def _related(doc: DocxDocument, bundle: ReportBundle) -> None:
    for report in bundle.candidates:
        doc.add_heading(report.display, level=2)
        if not report.related:
            doc.add_paragraph("No related records were found in the public data checked.")
            continue
        _table(
            doc,
            ("Relation", "Record", "Evidence", "Status"),
            [(r.relation, r.patent_key, r.evidence, "to verify") for r in report.related],
        )


def _commercial(doc: DocxDocument, bundle: ReportBundle) -> None:
    doc.add_paragraph(bundle.prose.get("commercial", ""))
    weights = bundle.weights
    doc.add_paragraph(
        f"Weights: commercial relevance {weights.commercial_relevance:.0%}, engineering effort "
        f"{weights.engineering_effort:.0%} (inverted), evidence quality "
        f"{weights.evidence_quality:.0%}, "
        f"unresolved risk {weights.unresolved_risk:.0%} (inverted). Scores run from 1 to 5.",
        style="Caption",
    )
    rows: list[tuple[str, ...]] = [
        (
            c.display,
            str(c.scores.commercial_relevance),
            str(c.scores.engineering_effort),
            str(c.scores.evidence_quality),
            str(c.scores.unresolved_risk),
            fmt_score(c.scores.total),
        )
        for c in bundle.candidates
        if c.scores
    ]
    _table(doc, ("Patent", "Commercial", "Effort", "Evidence", "Risk", "Total"), rows)


def _shortlist(doc: DocxDocument, bundle: ReportBundle) -> None:
    chosen: list[CandidateReport] = [
        c for c in bundle.candidates if c.recommendation == "Shortlist"
    ]
    if not chosen:
        doc.add_paragraph("No candidate is recommended.")
    for report in chosen:
        doc.add_heading(f"{report.display}: {report.title}", level=2)
        rationale: str = report.opportunity.rationale if report.opportunity else ""
        doc.add_paragraph(rationale or "No rationale was generated.")
        if report.reviewer_note:
            doc.add_paragraph(f"Reviewer note: {report.reviewer_note}")


def _next_steps(doc: DocxDocument, bundle: ReportBundle) -> None:
    doc.add_paragraph(bundle.prose.get("next_steps", ""))
    _bullets(
        doc,
        [
            "Confirm each status in USPTO Patent Center and check for a pending petition.",
            "Read the full claims and drawings; build a test sample before tooling.",
            "Have a patent attorney run a freedom-to-operate search, including related patents.",
            "Check design patents and trade dress that may cover the product's look.",
        ],
    )


def _limitations(doc: DocxDocument, bundle: ReportBundle) -> None:
    doc.add_paragraph(LABEL, style="Disclaimer")
    doc.add_heading("Limitations", level=2)
    _bullets(doc, bundle.limitations)
    doc.add_heading("Key assumptions", level=2)
    _bullets(doc, bundle.key_assumptions)
    doc.add_heading("Quality of information", level=2)
    _bullets(doc, bundle.quality_of_information)
    doc.add_heading("References", level=2)
    for number, reference in enumerate(bundle.references, start=1):
        paragraph = doc.add_paragraph(
            f"[{number}] {reference.title}. Retrieved {reference.retrieved}. "
        )
        if reference.url.startswith("http"):
            add_hyperlink(paragraph, reference.url, reference.url)
