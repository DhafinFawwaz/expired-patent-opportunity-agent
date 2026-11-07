from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.presentation import Presentation as Deck
from pptx.table import Table
from pptx.util import Inches

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.deck_content import SLIDES
from patentic.report.docx_renderer import COMPARISON_HEADER
from patentic.report.formatters import fmt_score, fmt_status
from patentic.report.pptx_renderer import render_pptx
from tests.report.helpers import TEMPLATES


@pytest.fixture(scope="module")
def deck(bundle: ReportBundle, tmp_path_factory: pytest.TempPathFactory) -> Deck:
    path: Path = render_pptx(
        bundle, TEMPLATES / "deck_template.pptx", tmp_path_factory.mktemp("pptx") / "deck.pptx"
    )
    return Presentation(str(path))


def slide_texts(deck: Deck) -> list[str]:
    return [
        "\n".join(shape.text_frame.text for shape in slide.shapes if shape.has_text_frame)
        for slide in deck.slides
    ]


def comparison_table(deck: Deck) -> Table:
    tables: list[Table] = [
        shape.table for slide in deck.slides for shape in slide.shapes if shape.has_table
    ]
    return next(t for t in tables if tuple(c.text for c in t.rows[0].cells) == COMPARISON_HEADER)


NAVY: RGBColor = RGBColor(0x1F, 0x3A, 0x5F)  # type: ignore[no-untyped-call]
NAVY_TINT: RGBColor = RGBColor(0xE9, 0xEE, 0xF5)  # type: ignore[no-untyped-call]


def test_deck_has_nine_slides_and_titles(deck: Deck) -> None:
    titles: list[str] = [s.shapes.title.text if s.shapes.title else "" for s in deck.slides]
    assert len(titles) == 9
    assert titles[1:] == list(SLIDES[1:])


def test_label_on_title_last_and_every_content_slide_footer(deck: Deck) -> None:
    texts: list[str] = slide_texts(deck)
    assert all(LABEL in text for text in texts)


def test_slide_size_16_9(deck: Deck) -> None:
    assert (deck.slide_width, deck.slide_height) == (Inches(13.333), Inches(7.5))


def test_chart_values_match_bundle_scores(bundle: ReportBundle, deck: Deck) -> None:
    chart = next(shape.chart for slide in deck.slides for shape in slide.shapes if shape.has_chart)
    values: list[float] = list(chart.plots[0].series[0].values)
    assert values == [round(c.scores.total, 2) for c in bundle.candidates if c.scores]


def test_candidate_table_roundtrip_matches_bundle(bundle: ReportBundle, deck: Deck) -> None:
    table = comparison_table(deck)
    rows = list(table.rows)[1:]
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


def test_notes_contain_evidence_ids(bundle: ReportBundle, deck: Deck) -> None:
    notes: str = "\n".join(
        s.notes_slide.notes_text_frame.text for s in deck.slides if s.has_notes_slide
    )
    assert all(e in notes for c in bundle.candidates for e in c.evidence_ids)


def test_title_slide_is_navy(deck: Deck) -> None:
    assert deck.slides[0].background.fill.fore_color.rgb == NAVY


def test_shortlisted_rows_are_tinted(bundle: ReportBundle, deck: Deck) -> None:
    rows = list(comparison_table(deck).rows)[1:]
    tinted: list[str] = [
        r.cells[0].text for r in rows if r.cells[0].fill.fore_color.rgb == NAVY_TINT
    ]
    assert tinted == [c.display for c in bundle.candidates if c.recommendation == "Shortlist"]


def test_chart_marks_shortlisted_bars(bundle: ReportBundle, deck: Deck) -> None:
    chart = next(shape.chart for slide in deck.slides for shape in slide.shapes if shape.has_chart)
    assert not chart.has_legend
    points = chart.plots[0].series[0].points
    scored = [c for c in bundle.candidates if c.scores]
    navy: list[bool] = [points[i].format.fill.fore_color.rgb == NAVY for i in range(len(scored))]
    assert navy == [c.recommendation == "Shortlist" for c in scored]


def test_every_content_slide_has_a_footer_with_its_number(deck: Deck) -> None:
    for number, slide in enumerate(list(deck.slides)[1:], start=2):
        texts: list[str] = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
        assert any(t.endswith(f"{number} / 9") for t in texts)
