import re
from pathlib import Path

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.deck_content import SLIDES
from patentic.report.html_deck import render_html
from patentic.report.validate import bundle_facts, extract_html_facts


def _render(bundle: ReportBundle, tmp_path: Path) -> str:
    return render_html(bundle, tmp_path / "deck.html").read_text()


def test_html_deck_has_the_nine_slides_in_order(bundle: ReportBundle, tmp_path: Path) -> None:
    page: str = _render(bundle, tmp_path)
    titles: list[str] = re.findall(r'<section class="slide[^"]*" data-title="([^"]+)"', page)
    assert titles == list(SLIDES)


def test_every_slide_carries_the_label(bundle: ReportBundle, tmp_path: Path) -> None:
    page: str = _render(bundle, tmp_path)
    slides: list[str] = page.split('<section class="slide')[1:]
    assert len(slides) == len(SLIDES)
    assert all(LABEL in slide for slide in slides)


def test_html_candidate_table_matches_bundle(bundle: ReportBundle, tmp_path: Path) -> None:
    path: Path = render_html(bundle, tmp_path / "deck.html")
    assert extract_html_facts(path).candidates == bundle_facts(bundle)


def test_synthetic_candidates_are_marked(bundle: ReportBundle, tmp_path: Path) -> None:
    assert any(c.is_synthetic for c in bundle.candidates)
    assert "SYNTHETIC FIXTURE" in _render(bundle, tmp_path)


def test_html_is_self_contained(bundle: ReportBundle, tmp_path: Path) -> None:
    page: str = _render(bundle, tmp_path)
    assert not re.search(r'<(script|link|img)[^>]+(src|href)="https?:', page)
    assert "<style>" in page
    assert "<script>" in page


def test_text_is_escaped(bundle: ReportBundle, tmp_path: Path) -> None:
    first: CandidateReport = bundle.candidates[0].model_copy(
        update={"title": "Mop <script>alert(1)</script>"}
    )
    hostile: ReportBundle = bundle.model_copy(
        update={"candidates": [first, *bundle.candidates[1:]]}
    )
    page: str = _render(hostile, tmp_path)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
