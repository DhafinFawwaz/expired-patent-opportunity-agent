from pathlib import Path

import pytest
from docx import Document
from docx.document import Document as DocxDocument
from docx.table import Table

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.docx_renderer import SECTIONS, render_docx
from patentic.report.formatters import fmt_score, fmt_status
from tests.report.helpers import TEMPLATES


@pytest.fixture(scope="module")
def docx_path(bundle: ReportBundle, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_docx(
        bundle, TEMPLATES / "report_template.docx", tmp_path_factory.mktemp("docx") / "report.docx"
    )


def open_doc(path: Path) -> DocxDocument:
    return Document(str(path))


def headings(doc: DocxDocument) -> list[str]:
    return [p.text for p in doc.paragraphs if p.style is not None and p.style.name == "Heading 1"]


def comparison(doc: DocxDocument) -> Table:
    return next(
        t for t in doc.tables if t.rows[0].cells[0].text == "Patent" and len(t.columns) == 6
    )


def test_docx_has_ten_sections_in_order(docx_path: Path) -> None:
    assert headings(open_doc(docx_path)) == [
        f"{i}. {title}" for i, title in enumerate(SECTIONS, start=1)
    ]


def test_label_in_header_title_and_section_ten(docx_path: Path) -> None:
    doc: DocxDocument = open_doc(docx_path)
    assert LABEL in doc.sections[0].header.paragraphs[0].text
    texts: list[str] = [p.text for p in doc.paragraphs]
    assert LABEL in texts[:4]
    section_ten: int = texts.index(f"10. {SECTIONS[9]}")
    assert texts[section_ten + 1] == LABEL
    assert doc.core_properties.subject == LABEL


def test_candidate_table_roundtrip(bundle: ReportBundle, docx_path: Path) -> None:
    rows = comparison(open_doc(docx_path)).rows[1:]
    found: dict[str, tuple[str, str, str]] = {
        r.cells[0].text: (r.cells[2].text, r.cells[4].text, r.cells[5].text) for r in rows
    }
    expected: dict[str, tuple[str, str, str]] = {
        c.display: (
            fmt_status(c.status.label),
            fmt_score(c.scores.total if c.scores else None),
            c.recommendation,
        )
        for c in bundle.candidates
    }
    assert found == expected


def test_synthetic_table_separate_with_heading(docx_path: Path) -> None:
    texts: list[str] = [p.text for p in open_doc(docx_path).paragraphs]
    assert any(t.startswith("SYNTHETIC FIXTURE") for t in texts)


def test_references_hyperlinked(docx_path: Path) -> None:
    xml: str = open_doc(docx_path).element.xml
    assert "w:hyperlink" in xml


def test_timeline_table_per_candidate(bundle: ReportBundle, docx_path: Path) -> None:
    timelines: list[Table] = [
        t for t in open_doc(docx_path).tables if t.rows[0].cells[0].text == "Date"
    ]
    assert len(timelines) == len(bundle.candidates) + (1 if bundle.illustration else 0)


def test_empty_related_records_renders_sentence_not_empty_table(
    bundle: ReportBundle, tmp_path: Path
) -> None:
    lonely: ReportBundle = bundle.model_copy(
        update={"candidates": [c.model_copy(update={"related": []}) for c in bundle.candidates]}
    )
    doc: DocxDocument = open_doc(
        render_docx(lonely, TEMPLATES / "report_template.docx", tmp_path / "r.docx")
    )
    texts: list[str] = [p.text for p in doc.paragraphs]
    assert any("No related records" in t for t in texts)
