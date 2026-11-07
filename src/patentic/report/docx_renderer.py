from collections.abc import Sequence
from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.shared import Pt
from docx.table import Table as DocxTable

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.oxml import add_hyperlink, repeat_header_row, shade_header_row
from patentic.report.report_content import (
    COMPARISON_HEADER,
    SECTIONS,
    Block,
    Bullets,
    Heading,
    PageBreak,
    Para,
    Reference,
    Table,
    report_blocks,
    report_meta,
    report_title,
)

__all__ = ["COMPARISON_HEADER", "SECTIONS", "render_docx"]

_STYLE: dict[str, str | None] = {
    "body": None,
    "caption": "Caption",
    "disclaimer": "Disclaimer",
    "banner": None,
}


def render_docx(bundle: ReportBundle, template: Path, out: Path) -> Path:
    doc: DocxDocument = Document(str(template))
    doc.core_properties.title = report_title(bundle)
    doc.core_properties.subject = LABEL
    doc.core_properties.author = "patentic"
    header = doc.sections[0].header.paragraphs[0]
    header.text = f"{LABEL}  Run {bundle.run.thread_id}"
    doc.add_heading(report_title(bundle), level=0)
    doc.add_paragraph(report_meta(bundle))
    doc.add_paragraph(LABEL, style="Disclaimer")
    for block in report_blocks(bundle):
        _write(doc, block)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


def _write(doc: DocxDocument, block: Block) -> None:
    if isinstance(block, Heading):
        doc.add_heading(block.text, level=block.level)
    elif isinstance(block, Para):
        doc.add_paragraph(block.text, style=_STYLE[block.kind])
    elif isinstance(block, Bullets):
        for item in block.items:
            doc.add_paragraph(item, style="List Bullet")
    elif isinstance(block, Table):
        _table(doc, block.header, block.rows)
    elif isinstance(block, PageBreak):
        doc.add_page_break()  # type: ignore[no-untyped-call]
    else:
        _reference(doc, block)


def _reference(doc: DocxDocument, ref: Reference) -> None:
    paragraph = doc.add_paragraph(f"[{ref.number}] {ref.title}. Retrieved {ref.retrieved}. ")
    if ref.url.startswith("http"):
        add_hyperlink(paragraph, ref.url, ref.url)


def _table(doc: DocxDocument, header: Sequence[str], rows: Sequence[Sequence[str]]) -> DocxTable:
    table: DocxTable = doc.add_table(rows=1, cols=len(header))
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
