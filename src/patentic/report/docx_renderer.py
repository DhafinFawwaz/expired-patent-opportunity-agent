import re
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from docx import Document
from docx.document import Document as DocxDocument
from docx.shared import Inches, Pt, RGBColor
from docx.table import Table as DocxTable
from docx.table import _Cell
from docx.text.paragraph import Paragraph

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.oxml import (
    add_hyperlink,
    border,
    full_width,
    repeat_header_row,
    shade_paragraph,
    style_cell,
)
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

# Colours follow the approved HTML report (assets/report.css).
NAVY: Final[str] = "1F3A5F"
NAVY_TINT: Final[str] = "E9EEF5"
AMBER_TINT: Final[str] = "FBF0E1"
INK: Final[str] = "17202B"
RULE: Final[str] = "DDE2E8"
_STYLE: Final[dict[str, str]] = {
    "body": "Normal",
    "caption": "Caption",
    "disclaimer": "Disclaimer",
    "banner": "Banner",
}
_NUMBERED: Final[re.Pattern[str]] = re.compile(r"(\d+\.) (.+)")
TEXT_WIDTH: Final[float] = 6.8
_COMPARISON_WIDTHS: Final[tuple[float, ...]] = (1.0, 2.25, 1.2, 0.8, 0.55, 1.0)


def column_widths(block: Table) -> tuple[float, ...]:
    if block.role == "comparison":
        return _COMPARISON_WIDTHS
    columns: list[list[str]] = [[row[i] for row in block.rows] for i in range(len(block.header))]
    weights: list[float] = [
        max(len(head), min(max((len(v) for v in values), default=0), 48), 6)
        for head, values in zip(block.header, columns, strict=True)
    ]
    total: float = sum(weights)
    return tuple(TEXT_WIDTH * w / total for w in weights)


def render_docx(bundle: ReportBundle, template: Path, out: Path) -> Path:
    doc: DocxDocument = Document(str(template))
    doc.core_properties.title = report_title(bundle)
    doc.core_properties.subject = LABEL
    doc.core_properties.author = "patentic"
    header: Paragraph = doc.sections[0].header.paragraphs[0]
    header.text = f"{LABEL}\tRun {bundle.run.thread_id}"
    border(header, ("bottom",), RULE, 4, 4)
    _cover(doc, bundle)
    for block in report_blocks(bundle):
        _write(doc, block)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


def _cover(doc: DocxDocument, bundle: ReportBundle) -> None:
    # A shaded cell, not paragraph shading: every viewer draws cell fills.
    band: DocxTable = doc.add_table(rows=1, cols=1)
    full_width(band)
    cell: _Cell = band.cell(0, 0)
    style_cell(cell, NAVY, 4, NAVY)
    title: Paragraph = cell.paragraphs[0]
    title.style = doc.styles["Title"]
    title.text = report_title(bundle)
    meta: Paragraph = cell.add_paragraph(report_meta(bundle), style="Cover Meta")
    for paragraph in (title, meta):
        paragraph.paragraph_format.left_indent = Inches(0.25)
        paragraph.paragraph_format.right_indent = Inches(0.25)
    title.paragraph_format.space_before = Pt(26)
    meta.paragraph_format.space_before = Pt(8)
    meta.paragraph_format.space_after = Pt(22)
    label: Paragraph = doc.add_paragraph(LABEL, style="Label")
    _boxed(label, NAVY_TINT)


def _boxed(paragraph: Paragraph, fill: str) -> None:
    shade_paragraph(paragraph, fill)
    border(paragraph, ("top", "left", "bottom", "right"), fill, 4, 6)
    paragraph.paragraph_format.left_indent = Inches(0.08)
    paragraph.paragraph_format.right_indent = Inches(0.08)


def _write(doc: DocxDocument, block: Block) -> None:
    if isinstance(block, Heading):
        _heading(doc, block)
    elif isinstance(block, Para):
        style: str = "Label" if block.text == LABEL else _STYLE[block.kind]
        paragraph: Paragraph = doc.add_paragraph(block.text, style=style)
        if style == "Label":
            _boxed(paragraph, NAVY_TINT)
        elif block.kind == "banner":
            _boxed(paragraph, AMBER_TINT)
    elif isinstance(block, Bullets):
        for item in block.items:
            doc.add_paragraph(item, style="List Bullet")
    elif isinstance(block, Table):
        _table(doc, block)
    elif isinstance(block, PageBreak):
        doc.add_page_break()  # type: ignore[no-untyped-call]
    else:
        _reference(doc, block)


def _heading(doc: DocxDocument, block: Heading) -> None:
    match: re.Match[str] | None = _NUMBERED.fullmatch(block.text)
    if block.level != 1 or match is None:
        doc.add_heading(block.text, level=block.level)
        return
    paragraph: Paragraph = doc.add_heading("", level=1)
    number, title = match.groups()
    paragraph.add_run(number).font.color.rgb = RGBColor.from_string(NAVY)
    paragraph.add_run(f" {title}")


def _reference(doc: DocxDocument, ref: Reference) -> None:
    paragraph: Paragraph = doc.add_paragraph(
        f"[{ref.number}] {ref.title}. Retrieved {ref.retrieved}. "
    )
    paragraph.paragraph_format.left_indent = Inches(0.3)
    paragraph.paragraph_format.first_line_indent = Inches(-0.3)
    for run in paragraph.runs:
        run.font.size = Pt(9)
    if ref.url.startswith("http"):
        add_hyperlink(paragraph, ref.url, ref.url)


def _cells(row_cells: Sequence[_Cell], values: Sequence[str], size: float, *, header: bool) -> None:
    for cell, text in zip(row_cells, values, strict=True):
        cell.text = text
        for paragraph in cell.paragraphs:
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.1
            for run in paragraph.runs:
                run.font.size = Pt(size)
                run.font.bold = header
                if header:
                    run.font.color.rgb = RGBColor.from_string("5B6573")


def _table(doc: DocxDocument, block: Table) -> DocxTable:
    table: DocxTable = doc.add_table(rows=1, cols=len(block.header))
    table.autofit = False
    full_width(table)
    _cells(table.rows[0].cells, block.header, 8.5, header=True)
    for cell in table.rows[0].cells:
        style_cell(cell, INK, 12)
    for index, row in enumerate(block.rows):
        cells = table.add_row().cells  # type: ignore[no-untyped-call]
        _cells(cells, row, 9, header=False)
        fill: str | None = NAVY_TINT if index in block.highlight else None
        for cell in cells:
            style_cell(cell, RULE, 4, fill)
    widths: tuple[float, ...] = column_widths(block)
    for column, width in zip(table.columns, widths, strict=True):
        column.width = Inches(width)
    for row in table.rows:
        for cell, width in zip(row.cells, widths, strict=True):
            cell.width = Inches(width)
    repeat_header_row(table)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table
