from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.presentation import Presentation as Deck
from pptx.shapes.autoshape import Shape
from pptx.slide import Slide
from pptx.table import Table, _Cell
from pptx.text.text import TextFrame, _Paragraph
from pptx.util import Emu, Pt

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.deck_content import (
    COMMERCIAL_NOTES,
    FLOW,
    NEXT_STEPS,
    SLIDES,
    WORKFLOW_NOTES,
    all_evidence,
    narrowing,
    objective,
    risks,
    shortlisted,
    sources,
)
from patentic.report.docx_renderer import COMPARISON_HEADER
from patentic.report.formatters import fmt_confidence, fmt_date, fmt_score, fmt_source, fmt_status

# Colours, sizes and positions follow the approved HTML deck (assets/deck.css) on its 1280x720 grid.
INK: Final[RGBColor] = RGBColor(0x17, 0x20, 0x2B)
MUTED: Final[RGBColor] = RGBColor(0x5B, 0x65, 0x73)
RULE: Final[RGBColor] = RGBColor(0xDD, 0xE2, 0xE8)
NAVY: Final[RGBColor] = RGBColor(0x1F, 0x3A, 0x5F)
NAVY_TINT: Final[RGBColor] = RGBColor(0xE9, 0xEE, 0xF5)
AMBER: Final[RGBColor] = RGBColor(0xA8, 0x5D, 0x0A)
AMBER_TINT: Final[RGBColor] = RGBColor(0xFB, 0xF0, 0xE1)
RUST: Final[RGBColor] = RGBColor(0x9C, 0x33, 0x24)
BAR_GREY: Final[RGBColor] = RGBColor(0xB9, 0xC3, 0xCF)
ON_NAVY: Final[RGBColor] = RGBColor(0xD3, 0xDA, 0xE3)
WHITE: Final[RGBColor] = RGBColor(0xFF, 0xFF, 0xFF)
FONT: Final[str] = "Arial"
EMU_PER_PX: Final[int] = 9525
LEFT: Final[int] = 72
WIDTH: Final[int] = 1136
BODY_TOP: Final[int] = 176
FOOTER_TOP: Final[int] = 668
_TITLE_LAYOUT: Final[int] = 0
_TITLE_ONLY_LAYOUT: Final[int] = 5
PER_ROW: Final[int] = 6
_STATUS_COLOUR: Final[dict[str, RGBColor]] = {
    "expired_nonpayment": NAVY,
    "reinstated": AMBER,
    "conflicting": RUST,
}
_TAKEAWAYS: Final[dict[int, str]] = {
    2: "What the run was asked to find, and what it does not claim.",
    3: "A fixed workflow: code fetches and judges the evidence, the model only drafts text.",
    4: "{found} patents searched; {recommended} recommended for review.",
    5: "{scored} candidates scored; {shortlisted} shortlisted (highlighted).",
    6: "Every status is dated and sourced; a later official notice overrides an earlier one.",
    7: "What the shortlisted patents claim, and what a prototype would need to settle.",
    8: "How the candidates compare on the weighted score.",
    9: "Treat every candidate as a lead to check, not a product to build yet.",
}

Box = tuple[float, float, float, float]


def px(value: float) -> Emu:
    return Emu(round(value * EMU_PER_PX))


def size(css_px: float) -> Pt:
    return Pt(css_px * 0.75)


def render_pptx(bundle: ReportBundle, template: Path, out: Path) -> Path:
    deck: Deck = Presentation(str(template))
    _title(deck, bundle)
    _objective(_content_slide(deck, bundle, 2), bundle)
    _workflow(_content_slide(deck, bundle, 3, "Amber boxes are human gates; the run pauses there."))
    _scope(_content_slide(deck, bundle, 4), bundle)
    _comparison(_content_slide(deck, bundle, 5, all_evidence(bundle)), bundle)
    _status_example(deck, bundle)
    _technical(_content_slide(deck, bundle, 7, all_evidence(bundle)), bundle)
    _commercial(deck, bundle)
    _risks(_content_slide(deck, bundle, 9), bundle)
    out.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(out))
    return out


def _style(
    paragraph: _Paragraph,
    css_px: float,
    colour: RGBColor = INK,
    *,
    bold: bool = False,
    after: float = 0,
) -> None:
    paragraph.space_after = size(after)
    for run in paragraph.runs:
        run.font.name = FONT
        run.font.size = size(css_px)
        run.font.bold = bold
        run.font.color.rgb = colour


def _frame(slide: Slide, box: Box) -> TextFrame:
    frame: TextFrame = slide.shapes.add_textbox(*(px(v) for v in box)).text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Emu(0)
    frame.vertical_anchor = MSO_ANCHOR.TOP
    return frame


def _add(frame: TextFrame, text: str) -> _Paragraph:
    first: bool = len(frame.paragraphs) == 1 and not frame.paragraphs[0].text
    paragraph: _Paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
    paragraph.text = text
    return paragraph


def _text(
    slide: Slide,
    box: Box,
    lines: Sequence[str],
    css_px: float,
    colour: RGBColor = INK,
    *,
    bold: bool = False,
    after: float = 0,
    align: PP_ALIGN = PP_ALIGN.LEFT,
) -> TextFrame:
    frame: TextFrame = _frame(slide, box)
    for line in lines:
        paragraph: _Paragraph = _add(frame, line)
        paragraph.alignment = align
        _style(paragraph, css_px, colour, bold=bold, after=after)
    return frame


def _rect(
    slide: Slide,
    box: Box,
    fill: RGBColor | None,
    line: RGBColor | None = None,
    *,
    rounded: bool = False,
) -> Shape:
    kind: MSO_SHAPE = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape: Shape = slide.shapes.add_shape(kind, *(px(v) for v in box))
    if rounded:
        shape.adjustments[0] = 0.06
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = px(1)
    shape.shadow.inherit = False
    return shape


def _rule(
    slide: Slide, x: float, y: float, w: float, colour: RGBColor = RULE, h: float = 1
) -> None:
    _rect(slide, (x, y, w, h), colour)


def _place(shape: Shape, box: Box) -> TextFrame:
    shape.left, shape.top, shape.width, shape.height = (px(v) for v in box)
    frame: TextFrame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Emu(0)
    return frame


def _title(deck: Deck, bundle: ReportBundle) -> None:
    slide: Slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_LAYOUT])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = NAVY
    title = slide.shapes.title
    if title is not None:
        frame: TextFrame = _place(title, (LEFT, 200, 1000, 140))
        frame.text = f"Expired-patent screening: {bundle.request.technology_category}"
        frame.vertical_anchor = MSO_ANCHOR.BOTTOM
        for paragraph in frame.paragraphs:
            paragraph.alignment = PP_ALIGN.LEFT
            _style(paragraph, 50, WHITE, bold=True)
    sub: TextFrame = _place(slide.placeholders[1], (LEFT, 358, 1000, 36))
    sub.text = "US patents that appear to have lapsed for nonpayment of maintenance fees"
    sub.vertical_anchor = MSO_ANCHOR.TOP
    for paragraph in sub.paragraphs:
        paragraph.alignment = PP_ALIGN.LEFT
        _style(paragraph, 22, ON_NAVY)
    meta: list[str] = [
        f"Run {bundle.run.thread_id}",
        f"{bundle.run.created:%Y-%m-%d} · US patents only",
    ]
    _text(slide, (LEFT, 440, 900, 60), meta, 15, ON_NAVY, after=4)
    _text(slide, (LEFT, 660, 1100, 24), [LABEL], 14, WHITE)


def _content_slide(deck: Deck, bundle: ReportBundle, number: int, notes: str = "") -> Slide:
    slide: Slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_ONLY_LAYOUT])
    title = slide.shapes.title
    if title is not None:
        frame: TextFrame = _place(title, (LEFT, 48, WIDTH, 44))
        frame.text = SLIDES[number - 1]
        frame.vertical_anchor = MSO_ANCHOR.TOP
        for paragraph in frame.paragraphs:
            paragraph.alignment = PP_ALIGN.LEFT
            _style(paragraph, 32, INK, bold=True)
    values: dict[str, str] = {
        "found": f"{bundle.flow.found:,}",
        "recommended": str(bundle.flow.recommended),
        "scored": str(len(bundle.candidates)),
        "shortlisted": str(len(bundle.shortlist)),
    }
    _text(slide, (LEFT, 104, 1000, 28), [_TAKEAWAYS[number].format(**values)], 18, MUTED)
    _rule(slide, 0, FOOTER_TOP, 1280)
    _text(slide, (LEFT, 686, 760, 18), [LABEL], 12, MUTED)
    footer: str = f"Run {bundle.run.thread_id} · {number} / {len(SLIDES)}"
    _text(slide, (LEFT + WIDTH - 420, 686, 420, 18), [footer], 12, MUTED, align=PP_ALIGN.RIGHT)
    notes_frame = slide.notes_slide.notes_text_frame
    if notes and notes_frame is not None:
        notes_frame.text = notes
    return slide


def _empty(slide: Slide, text: str) -> None:
    _text(slide, (LEFT, BODY_TOP, WIDTH, 30), [text], 18, MUTED)


def _numbered(
    slide: Slide, x: float, y: float, w: float, lines: Sequence[str], step: float
) -> float:
    for number, line in enumerate(lines, start=1):
        _text(slide, (x, y + 14, 30, 30), [str(number)], 18, NAVY, bold=True)
        _text(slide, (x + 44, y + 14, w - 44, step - 16), [line], 18)
        y += step
        _rule(slide, x, y, w)
    return y


def _objective(slide: Slide, bundle: ReportBundle) -> None:
    request = bundle.request
    lead: str = request.technology_category.capitalize()
    _text(slide, (LEFT, BODY_TOP, 380, 80), [lead], 26, bold=True)
    _text(slide, (LEFT, BODY_TOP + 96, 380, 160), [request.intended_product or ""], 18, MUTED)
    _numbered(slide, LEFT + 428, BODY_TOP, WIDTH - 428, objective(bundle), 70)


def _workflow(slide: Slide) -> None:
    gap: float = 26
    w: float = (WIDTH - (PER_ROW - 1) * gap) / PER_ROW
    h: float = 74
    for index, (label, gate) in enumerate(FLOW):
        x: float = LEFT + (index % PER_ROW) * (w + gap)
        y: float = BODY_TOP + (index // PER_ROW) * (h + 22)
        fill: RGBColor = AMBER_TINT if gate else NAVY_TINT
        box: Shape = _rect(slide, (x, y, w, h), fill, AMBER if gate else RULE, rounded=True)
        frame: TextFrame = box.text_frame
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = px(14)
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        paragraph: _Paragraph = frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.LEFT
        number = paragraph.add_run()
        number.text = f"{index + 1}  "
        name = paragraph.add_run()
        name.text = label
        _style(paragraph, 15)
        number.font.bold = True
        number.font.color.rgb = NAVY
        if index % PER_ROW != PER_ROW - 1 and index != len(FLOW) - 1:
            _text(slide, (x + w + 8, y + 20, 12, 30), ["\u203a"], 22, MUTED)
    legend: float = BODY_TOP + 2 * h + 44
    _rect(slide, (LEFT, legend + 3, 12, 12), AMBER_TINT, AMBER)
    gates: str = "The run pauses for a person at these two steps."
    _text(slide, (LEFT + 20, legend, 600, 20), [gates], 14, MUTED)
    column: float = (WIDTH - 48) / 2
    for index, line in enumerate(WORKFLOW_NOTES):
        x = LEFT + index * (column + 48)
        _rule(slide, x, legend + 54, column)
        _text(slide, (x, legend + 68, column, 60), [line], 16)


def _scope(slide: Slide, bundle: ReportBundle) -> None:
    stages: list[tuple[str, int]] = narrowing(bundle)
    top: int = max((n for _, n in stages), default=0) or 1
    track: float = 300
    for index, (what, count) in enumerate(stages):
        y: float = BODY_TOP + index * 52
        _text(slide, (LEFT, y, track, 20), [what], 15)
        _rect(slide, (LEFT, y + 24, track, 14), NAVY_TINT)
        filled: float = max(count / top * track, 2 if count else 0)
        if filled:
            _rect(slide, (LEFT, y + 24, filled, 14), NAVY)
        box: Box = (LEFT + track + 12, y + 12, 68, 28)
        _text(slide, box, [f"{count:,}"], 22, bold=True, align=PP_ALIGN.RIGHT)
    x: float = LEFT + 428
    w: float = WIDTH - 428
    rows: list[tuple[str, ...]] = list(sources(bundle))
    _table(slide, (x, BODY_TOP, w), ("Source", "What it gave", "Grade"), rows, (170, w - 240, 70))
    cpc: str = ", ".join(bundle.plan.cpc_codes[:8]) or "n/a"
    below: float = BODY_TOP + 44 * (len(rows) + 1) + 14
    _text(slide, (x, below, w, 40), [f"CPC groups searched: {cpc}"], 14, MUTED)


def _table(
    slide: Slide,
    origin: tuple[float, float, float],
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Sequence[float],
    *,
    row_px: float = 44,
    css_px: float = 15,
) -> Table:
    x, y, w = origin
    height: Emu = px(row_px * (len(rows) + 1))
    table: Table = slide.shapes.add_table(
        len(rows) + 1, len(header), px(x), px(y), px(w), height
    ).table
    table.first_row = False
    table.horz_banding = False
    for index, width in enumerate(widths):
        table.columns[index].width = px(width)
    for row in table.rows:
        row.height = px(row_px)
    for column, text in enumerate(header):
        _cell(table.cell(0, column), text, 13, MUTED, bold=True, bottom=INK, weight=2)
    for r, values in enumerate(rows, start=1):
        for column, text in enumerate(values):
            _cell(table.cell(r, column), text, css_px)
    return table


def _cell(
    cell: _Cell,
    text: str,
    css_px: float,
    colour: RGBColor = INK,
    *,
    bold: bool = False,
    bottom: RGBColor = RULE,
    weight: float = 1,
) -> None:
    cell.text = text
    cell.fill.solid()
    cell.fill.fore_color.rgb = WHITE
    cell.margin_left = cell.margin_right = cell.margin_top = cell.margin_bottom = px(8)
    cell.vertical_anchor = MSO_ANCHOR.TOP
    for paragraph in cell.text_frame.paragraphs:
        _style(paragraph, css_px, colour, bold=bold)
    _borders(cell, bottom, weight)


def _borders(cell: _Cell, bottom: RGBColor, weight: float) -> None:
    # python-pptx has no border API; tcPr wants lnL, lnR, lnT, lnB ahead of the fill.
    properties = cell._tc.get_or_add_tcPr()  # noqa: SLF001
    for side in ("lnL", "lnR", "lnT", "lnB"):
        for old in properties.findall(qn(f"a:{side}")):
            properties.remove(old)
    lines: list[str] = [
        f'<a:{s} {nsdecls("a")} w="0"><a:noFill/></a:{s}>' for s in ("lnL", "lnR", "lnT")
    ]
    lines.append(
        f'<a:lnB {nsdecls("a")} w="{px(weight)}" cap="flat" cmpd="sng">'
        f'<a:solidFill><a:srgbClr val="{bottom}"/></a:solidFill><a:prstDash val="solid"/></a:lnB>'
    )
    for index, xml in enumerate(lines):
        properties.insert(index, parse_xml(xml))


def _comparison(slide: Slide, bundle: ReportBundle) -> None:
    if not bundle.candidates:
        _empty(slide, "No candidate passed the evidence and screening checks.")
        return
    y: float = BODY_TOP
    if any(c.is_synthetic for c in bundle.candidates):
        banner: Shape = _rect(slide, (LEFT, y, WIDTH, 34), AMBER_TINT)
        frame: TextFrame = banner.text_frame
        frame.margin_left = px(12)
        frame.text = "SYNTHETIC FIXTURE: made-up patents used to test the pipeline."
        frame.paragraphs[0].alignment = PP_ALIGN.LEFT
        _style(frame.paragraphs[0], 14, AMBER, bold=True)
        y += 48
    rows: list[tuple[str, ...]] = [
        (
            c.display,
            c.title,
            fmt_status(c.status.label),
            fmt_confidence(c.status.confidence),
            fmt_score(c.scores.total if c.scores else None),
            c.recommendation,
        )
        for c in bundle.candidates
    ]
    widths: tuple[float, ...] = (130, 476, 170, 110, 80, 170)
    table: Table = _table(slide, (LEFT, y, WIDTH), COMPARISON_HEADER, rows, widths, row_px=46)
    for r, candidate in enumerate(bundle.candidates, start=1):
        if candidate.recommendation == "Shortlist":
            for column in range(len(COMPARISON_HEADER)):
                table.cell(r, column).fill.fore_color.rgb = NAVY_TINT
        status = table.cell(r, 2).text_frame.paragraphs[0].runs[0]
        status.font.color.rgb = _STATUS_COLOUR.get(candidate.status.label, MUTED)


def _status_example(deck: Deck, bundle: ReportBundle) -> None:
    example: CandidateReport | None = bundle.illustration or (
        bundle.candidates[0] if bundle.candidates else None
    )
    notes: str = ("Evidence: " + ", ".join(example.evidence_ids)) if example else ""
    slide: Slide = _content_slide(deck, bundle, 6, notes)
    if example is None:
        _empty(slide, "No status example is available for this run.")
        return
    paragraph: _Paragraph = _frame(slide, (LEFT, BODY_TOP, 788, 30)).paragraphs[0]
    colour: RGBColor = _STATUS_COLOUR.get(example.status.label, MUTED)
    for text, bold, tint in (
        (f"{example.display} ", True, INK),
        (f"{example.title} · ", False, INK),
        (fmt_status(example.status.label), True, colour),
        (f" · confidence {fmt_confidence(example.status.confidence)}", False, INK),
    ):
        run = paragraph.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = size(18)
        run.font.bold = bold
        run.font.color.rgb = tint
    rows: list[tuple[str, ...]] = [
        (fmt_date(r.date), r.event, f"{fmt_source(r.source)} ({r.grade})")
        for r in example.timeline[:10]
    ]
    table: Table = _table(
        slide,
        (LEFT, BODY_TOP + 44, 788),
        ("Date", "Event", "Source"),
        rows,
        (110, 388, 290),
        row_px=34,
        css_px=14,
    )
    for r in range(1, len(rows) + 1):
        for column in (0, 2):
            table.cell(r, column).text_frame.paragraphs[0].runs[0].font.color.rgb = MUTED
    note: str = bundle.illustration_note or " ".join(example.status.notes)
    box: Shape = _rect(slide, (LEFT + 836, BODY_TOP, 300, 270), NAVY_TINT)
    frame: TextFrame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = px(18)
    frame.margin_top = frame.margin_bottom = px(16)
    frame.vertical_anchor = MSO_ANCHOR.TOP
    frame.text = note
    frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    _style(frame.paragraphs[0], 15)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _technical(slide: Slide, bundle: ReportBundle) -> None:
    chosen: list[CandidateReport] = shortlisted(bundle)
    if not chosen:
        _empty(slide, "No candidate was shortlisted, so no technical opportunity is presented.")
        return
    width: float = (WIDTH - 48) / 2
    for index, report in enumerate(chosen[:2]):
        tech = report.technical
        if tech is None:
            continue
        x: float = LEFT + index * (width + 48)
        _rect(slide, (x, BODY_TOP, width, 476), None, RULE, rounded=True)
        frame: TextFrame = _frame(slide, (x + 24, BODY_TOP + 20, width - 48, 436))
        _style(_add(frame, report.display), 14, NAVY, bold=True, after=4)
        _style(_add(frame, _clip(report.title, 110)), 18, bold=True, after=10)
        _style(_add(frame, _clip(tech.summary, 330)), 15, after=12)
        _style(_add(frame, "Key claim elements"), 13, MUTED, bold=True, after=4)
        for item in tech.key_claim_elements[:3]:
            _style(_add(frame, "• " + _clip(item, 120)), 14, after=4)
        _style(_add(frame, "Open questions"), 13, MUTED, bold=True, after=4)
        for item in tech.implementation_unknowns[:3] or ["None recorded"]:
            _style(_add(frame, "• " + _clip(item, 120)), 14, after=4)


def _commercial(deck: Deck, bundle: ReportBundle) -> None:
    weights = bundle.weights
    weight_text: str = (
        f"Weights: commercial relevance {weights.commercial_relevance:.0%}, engineering effort "
        f"{weights.engineering_effort:.0%}, evidence quality {weights.evidence_quality:.0%}, "
        f"unresolved risk {weights.unresolved_risk:.0%}."
    )
    slide: Slide = _content_slide(deck, bundle, 8, weight_text)
    scored: list[CandidateReport] = [c for c in bundle.candidates if c.scores]
    if not scored:
        _empty(slide, "No candidate was scored.")
        return
    data: CategoryChartData = CategoryChartData()
    data.categories = [c.display for c in scored]
    data.add_series("Total score", [round(c.scores.total, 2) for c in scored if c.scores])
    height: float = min(60 * len(scored) + 40, 400)
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED,
        px(LEFT),
        px(BODY_TOP - 10),
        px(740),
        px(height),
        data,  # type: ignore[arg-type]  # CategoryChartData is a ChartData at runtime
    ).chart  # type: ignore[attr-defined]  # the stub types add_chart's frame as Chart
    chart.has_legend = False
    chart.font.name = FONT
    chart.font.size = size(15)
    chart.font.color.rgb = INK
    plot = chart.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.number_format = "0.0"
    labels.number_format_is_linked = False
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    labels.font.bold = True
    for index, candidate in enumerate(scored):
        point = plot.series[0].points[index]
        point.format.fill.solid()
        shortlist: bool = candidate.recommendation == "Shortlist"
        point.format.fill.fore_color.rgb = NAVY if shortlist else BAR_GREY
    category = chart.category_axis
    category.reverse_order = True
    category.format.line.fill.background()
    category.has_major_gridlines = False
    value = chart.value_axis
    value.minimum_scale = 0
    value.maximum_scale = 5
    value.has_major_gridlines = False
    value.visible = False
    caption: str = "Total score out of 5. Navy bars are shortlisted."
    _text(slide, (LEFT, BODY_TOP + height, 740, 20), [caption], 13, MUTED)
    x: float = LEFT + 788
    w: float = WIDTH - 788
    bullets: list[str] = ["• " + line for line in COMMERCIAL_NOTES]
    _text(slide, (x, BODY_TOP, w, 300), bullets, 18, after=10)
    _text(slide, (x, BODY_TOP + 300, w, 60), [weight_text], 14, MUTED)


def _risks(slide: Slide, bundle: ReportBundle) -> None:
    width: float = (WIDTH - 48) / 2
    _text(slide, (LEFT, BODY_TOP, width, 26), ["Unresolved risks"], 18, bold=True)
    bullets: list[str] = ["• " + line for line in risks(bundle)]
    _text(slide, (LEFT, BODY_TOP + 40, width, 300), bullets, 18, after=10)
    x: float = LEFT + width + 48
    _text(slide, (x, BODY_TOP, width, 26), ["Next steps"], 18, bold=True)
    end: float = _numbered(slide, x, BODY_TOP + 40, width, NEXT_STEPS, 76)
    _rule(slide, x, end + 28, width, INK, 2)
    _text(slide, (x, end + 42, width, 50), [LABEL], 16, bold=True)
