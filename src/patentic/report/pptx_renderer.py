from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Final

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.presentation import Presentation as Deck
from pptx.slide import Slide
from pptx.util import Emu, Inches, Pt

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.deck_content import (
    COMMERCIAL_NOTES,
    FLOW,
    SLIDES,
    WORKFLOW_NOTES,
    all_evidence,
    objective,
    risks,
    scope,
    technical,
)
from patentic.report.docx_renderer import COMPARISON_HEADER
from patentic.report.formatters import fmt_confidence, fmt_date, fmt_score, fmt_source, fmt_status

_TITLE_LAYOUT: Final[int] = 0
_TITLE_ONLY_LAYOUT: Final[int] = 5
_GREY: Final[RGBColor] = RGBColor(0x59, 0x59, 0x59)
_GATE: Final[RGBColor] = RGBColor(0xF4, 0xB1, 0x83)
_STEP: Final[RGBColor] = RGBColor(0xD9, 0xE2, 0xF3)
_FLOW: Final[tuple[tuple[str, bool], ...]] = FLOW


def render_pptx(bundle: ReportBundle, template: Path, out: Path) -> Path:
    deck: Deck = Presentation(str(template))
    _title(deck, bundle)
    _text_slide(deck, SLIDES[1], objective(bundle), all_evidence(bundle))
    _workflow(deck)
    _text_slide(deck, SLIDES[3], scope(bundle), "")
    _comparison(deck, bundle)
    _status_example(deck, bundle)
    _text_slide(deck, SLIDES[6], technical(bundle), all_evidence(bundle))
    _commercial(deck, bundle)
    _text_slide(deck, SLIDES[8], _risks(bundle), "")
    out.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(out))
    return out


def _content_slide(deck: Deck, title: str, notes: str) -> Slide:
    slide: Slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_ONLY_LAYOUT])
    if slide.shapes.title is not None:
        slide.shapes.title.text = title
    footer = slide.shapes.add_textbox(
        Inches(0.5), Inches(6.9), Inches(12.3), Inches(0.4)
    ).text_frame
    footer.text = LABEL
    footer.paragraphs[0].runs[0].font.size = Pt(10)
    footer.paragraphs[0].runs[0].font.color.rgb = _GREY
    notes_frame = slide.notes_slide.notes_text_frame
    if notes and notes_frame is not None:
        notes_frame.text = notes
    return slide


def _write_lines(slide: Slide, lines: Sequence[str], top: float = 1.5, size: int = 16) -> None:
    frame = slide.shapes.add_textbox(Inches(0.6), Inches(top), Inches(12.1), Inches(5.2)).text_frame
    frame.word_wrap = True
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.space_after = Pt(8)
        for run in paragraph.runs:
            run.font.size = Pt(size)


def _text_slide(deck: Deck, title: str, lines: Sequence[str], notes: str) -> None:
    _write_lines(_content_slide(deck, title, notes), lines)


def _title(deck: Deck, bundle: ReportBundle) -> None:
    slide: Slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_LAYOUT])
    if slide.shapes.title is not None:
        slide.shapes.title.text = f"Expired-patent screening: {bundle.request.technology_category}"
    subtitle = slide.placeholders[1].text_frame
    assert subtitle is not None  # noqa: S101  # the title layout always has a subtitle
    subtitle.text = f"US patents only. Run {bundle.run.thread_id}, {bundle.run.created:%Y-%m-%d}."
    subtitle.add_paragraph().text = LABEL


def _workflow(deck: Deck) -> None:
    slide: Slide = _content_slide(
        deck, SLIDES[2], "Orange boxes are human gates; the run pauses there."
    )
    width: float = 2.1
    height: float = 0.8
    positions: list[tuple[float, float]] = [
        (0.5 + (i % 6) * (width + 0.05), 1.7 + (i // 6) * 1.6) for i in range(len(_FLOW))
    ]
    shapes = []
    for (label, gate), (left, top) in zip(_FLOW, positions, strict=True):
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
        )
        box.fill.solid()
        box.fill.fore_color.rgb = _GATE if gate else _STEP
        box.line.color.rgb = _GREY
        box.text_frame.text = label
        box.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        box.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(0, 0, 0)
        shapes.append(box)
    for first, second in pairwise(shapes):
        connector = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT,
            Emu(first.left + first.width),
            Emu(first.top + first.height // 2),
            Emu(second.left),
            Emu(second.top + second.height // 2),
        )
        connector.line.color.rgb = _GREY
    _write_lines(
        slide,
        WORKFLOW_NOTES,
        top=5.0,
        size=14,
    )


def _comparison(deck: Deck, bundle: ReportBundle) -> None:
    synthetic: bool = any(c.is_synthetic for c in bundle.candidates)
    title: str = SLIDES[4]
    slide: Slide = _content_slide(deck, title, all_evidence(bundle))
    if synthetic:
        _write_lines(
            slide,
            ["SYNTHETIC FIXTURE: made-up patents used to test the pipeline."],
            top=1.2,
            size=12,
        )
    if not bundle.candidates:
        _write_lines(slide, ["No candidate passed the evidence and screening checks."])
        return
    rows: int = len(bundle.candidates) + 1
    table = slide.shapes.add_table(
        rows, len(COMPARISON_HEADER), Inches(0.5), Inches(1.7), Inches(12.3), Inches(0.4 * rows)
    ).table
    for column, text in enumerate(COMPARISON_HEADER):
        table.cell(0, column).text = text
    for row, report in enumerate(bundle.candidates, start=1):
        values: tuple[str, ...] = (
            report.display,
            report.title,
            fmt_status(report.status.label),
            fmt_confidence(report.status.confidence),
            fmt_score(report.scores.total if report.scores else None),
            report.recommendation,
        )
        for column, text in enumerate(values):
            table.cell(row, column).text = text
    for row_cells in table.rows:
        for cell in row_cells.cells:
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(12)


def _status_example(deck: Deck, bundle: ReportBundle) -> None:
    example: CandidateReport | None = bundle.illustration or (
        bundle.candidates[0] if bundle.candidates else None
    )
    notes: str = ("Evidence: " + ", ".join(example.evidence_ids)) if example else ""
    slide: Slide = _content_slide(deck, SLIDES[5], notes)
    if example is None:
        _write_lines(slide, ["No status example is available for this run."])
        return
    _write_lines(
        slide,
        [
            (
                f"{example.display}: {example.title}. {fmt_status(example.status.label)}, "
                f"confidence {fmt_confidence(example.status.confidence)}."
            ),
            bundle.illustration_note,
        ],
        top=1.2,
        size=13,
    )
    rows: list[tuple[str, str, str]] = [
        (fmt_date(r.date), r.event, f"{fmt_source(r.source)} ({r.grade})") for r in example.timeline
    ][:9]
    table = slide.shapes.add_table(
        len(rows) + 1, 3, Inches(0.5), Inches(2.6), Inches(12.3), Inches(0.35 * (len(rows) + 1))
    ).table
    for column, text in enumerate(("Date", "Event", "Source")):
        table.cell(0, column).text = text
    for row, values in enumerate(rows, start=1):
        for column, text in enumerate(values):
            table.cell(row, column).text = text
            for paragraph in table.cell(row, column).text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(11)


def _commercial(deck: Deck, bundle: ReportBundle) -> None:
    scored: list[CandidateReport] = [c for c in bundle.candidates if c.scores]
    slide: Slide = _content_slide(deck, SLIDES[7], "Weights: " + bundle.weights.model_dump_json())
    if not scored:
        _write_lines(slide, ["No candidate was scored."])
        return
    data: CategoryChartData = CategoryChartData()
    data.categories = [c.display for c in scored]
    data.add_series("Total score", [round(c.scores.total, 2) for c in scored if c.scores])
    slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED,
        Inches(0.5),
        Inches(1.5),
        Inches(7.5),
        Inches(5.0),
        data,  # type: ignore[arg-type]  # CategoryChartData is a ChartData at runtime
    )
    _write_lines_at(
        slide,
        COMMERCIAL_NOTES,
        left=8.3,
    )


def _write_lines_at(slide: Slide, lines: Sequence[str], left: float) -> None:
    frame = slide.shapes.add_textbox(Inches(left), Inches(1.6), Inches(4.5), Inches(5.0)).text_frame
    frame.word_wrap = True
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.space_after = Pt(10)
        for run in paragraph.runs:
            run.font.size = Pt(14)


def _risks(bundle: ReportBundle) -> list[str]:
    return [
        *risks(bundle),
        "Next: confirm status in Patent Center, read full claims, and have an attorney run a freedom-to-operate search.",
        LABEL,
    ]
