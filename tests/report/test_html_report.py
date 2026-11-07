import re
from pathlib import Path

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.html_report import render_report_html
from patentic.report.report_content import SECTIONS
from patentic.report.validate import bundle_facts, extract_html_facts


def _render(bundle: ReportBundle, tmp_path: Path) -> str:
    return render_report_html(bundle, tmp_path / "report.html").read_text()


def test_report_html_has_the_ten_sections_in_order(bundle: ReportBundle, tmp_path: Path) -> None:
    page: str = _render(bundle, tmp_path)
    titles: list[tuple[str, str]] = re.findall(
        r'<h1 id="s\d+"><span class="num">(\d+)\.</span> ([^<]+)</h1>', page
    )
    assert [t for _, t in titles] == list(SECTIONS)


def test_label_on_cover_every_page_and_section_ten(bundle: ReportBundle, tmp_path: Path) -> None:
    page: str = _render(bundle, tmp_path)
    sheets: list[str] = page.split('<article class="sheet')[1:]
    assert len(sheets) >= 4
    assert all(LABEL in sheet for sheet in sheets)
    assert LABEL in page.split('id="s10"')[1]


def test_report_html_candidate_table_matches_bundle(bundle: ReportBundle, tmp_path: Path) -> None:
    path: Path = render_report_html(bundle, tmp_path / "report.html")
    assert extract_html_facts(path).candidates == bundle_facts(bundle)


def test_synthetic_candidates_have_their_own_banner(bundle: ReportBundle, tmp_path: Path) -> None:
    assert "SYNTHETIC FIXTURE" in _render(bundle, tmp_path)


def test_report_html_is_self_contained_and_links_references(
    bundle: ReportBundle, tmp_path: Path
) -> None:
    page: str = _render(bundle, tmp_path)
    assert not re.search(r'<(script|link|img)[^>]+(src|href)="https?:', page)
    linked: list[str] = [r.url for r in bundle.references if r.url.startswith("http")]
    assert linked
    assert all(f'href="{url}"' in page for url in linked)


def test_report_html_escapes_text(bundle: ReportBundle, tmp_path: Path) -> None:
    first: CandidateReport = bundle.candidates[0].model_copy(update={"title": "Mop <b>x</b>"})
    hostile: ReportBundle = bundle.model_copy(
        update={"candidates": [first, *bundle.candidates[1:]]}
    )
    page: str = _render(hostile, tmp_path)
    assert "Mop <b>x</b>" not in page
    assert "Mop &lt;b&gt;x&lt;/b&gt;" in page
