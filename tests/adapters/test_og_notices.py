from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from patentic.adapters.http import HttpSource
from patentic.adapters.og_notices import (
    OgIndex,
    OgIndexer,
    OgPage,
    OgRow,
    archive_url,
    issue_tuesdays,
    mirror_url,
    og_week,
    parse_toc,
)
from patentic.domain.events import StatusEvent

DATA: Path = Path(__file__).parents[1] / "data" / "og"
AT: datetime = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)
PAGE_2026: str = (DATA / "2026-week44-excerpt.html").read_text()
PAGE_2015: str = (DATA / "2015-week40-excerpt.html").read_text()


def parse(html: str, url: str = "https://www.uspto.gov/og/2026/week44/TOC.htm") -> OgPage:
    return parse_toc(html, url, AT)


def test_parse_2026_page_rows_and_dates() -> None:
    page: OgPage = parse(PAGE_2026)
    assert page.issue_date == date(2026, 11, 3)
    assert page.citation == "1552 OG 3"
    expired: list[OgRow] = [r for r in page.rows if r.kind == "expired"]
    assert any(
        r.expired_on == date(2026, 9, 9) and r.issue_date == date(2014, 9, 9) for r in expired
    )
    reinstated: OgRow = next(r for r in page.rows if r.patent.key == "US-8646606")
    assert reinstated.kind == "reinstated"
    assert reinstated.granted_on == date(2026, 10, 7)
    assert reinstated.application == "13031042"


def test_parse_2015_two_digit_years() -> None:
    page: OgPage = parse(PAGE_2015)
    first: OgRow = next(r for r in page.rows if r.kind == "expired")
    assert first.patent.key == "US-6606751"
    assert first.issue_date == date(2003, 8, 19)
    assert first.expired_on == date(2015, 8, 19)


def test_parse_reissue_variants() -> None:
    keys: set[str] = {r.patent.key for r in parse(PAGE_2026).rows}
    assert {"US-RE46721", "US-RE47917"} <= keys


def test_parse_toc_without_reinstated_section() -> None:
    html: str = PAGE_2026.replace("Patents Reinstated Due to", "Something Else Due to")
    page: OgPage = parse(html)
    assert "reinstated" not in page.sections_found
    assert all(r.kind == "expired" for r in page.rows)


def test_rows_carry_evidence_with_grade_a() -> None:
    page: OgPage = parse(PAGE_2026)
    row: OgRow = page.rows[0]
    evidence = page.evidence_for(row)
    assert evidence.source == "og_notice"
    assert evidence.source_grade == "A"
    assert evidence.evidence_id == row.evidence_id
    assert evidence.url.endswith("#ref2")
    assert row.patent.display.replace(",", "") in evidence.raw_snippet.replace(",", "")


def test_keep_filter_limits_expired_rows_but_keeps_reinstatements() -> None:
    page: OgPage = parse_toc(PAGE_2026, "u", AT, keep={"US-8826466"})
    assert {r.patent.key for r in page.rows if r.kind == "expired"} == {"US-8826466"}
    assert any(r.kind == "reinstated" for r in page.rows)


def test_og_week_numbering() -> None:
    assert og_week(date(2026, 11, 3)) == (2026, 44)
    assert og_week(date(2026, 1, 6)) == (2026, 1)
    assert og_week(date(2015, 10, 6)) == (2015, 40)


def test_issue_tuesdays_counts_back_from_today() -> None:
    tuesdays: list[date] = issue_tuesdays(date(2026, 11, 7), 3)
    assert tuesdays == [date(2026, 11, 3), date(2026, 10, 27), date(2026, 10, 20)]


def test_urls() -> None:
    assert (
        archive_url(2026, 4) == "https://www.uspto.gov/web/offices/com/sol/og/2026/week04/TOC.htm"
    )
    assert mirror_url(44) == "https://patentsgazette.uspto.gov/week44/OG/TOC.htm"


def indexer(tmp_path: Path, handler: httpx.MockTransport) -> OgIndexer:
    http: HttpSource = HttpSource(
        name="og",
        cache_dir=tmp_path,
        ttl=None,
        rate_per_second=1000.0,
        user_agent="t",
        transport=handler,
        sleep=lambda _s: None,
    )
    return OgIndexer(http)


def test_fetch_window_skips_404_weeks(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if "week44" in request.url.path and "uspto.gov/web" in str(request.url):
            return httpx.Response(200, text=PAGE_2026)
        return httpx.Response(404)

    index: OgIndex = indexer(tmp_path, httpx.MockTransport(handle)).fetch_window(
        3, date(2026, 11, 7)
    )
    assert index.coverage.weeks_fetched == 1
    assert index.coverage.missing_weeks == [date(2026, 10, 27), date(2026, 10, 20)]
    assert index.coverage.last_issue == date(2026, 11, 3)
    assert index.coverage.as_of == date(2026, 11, 7)


def test_fetch_window_uses_mirror_when_archive_404s(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "patentsgazette.uspto.gov" and "week44" in request.url.path:
            return httpx.Response(200, text=PAGE_2026)
        return httpx.Response(404)

    index: OgIndex = indexer(tmp_path, httpx.MockTransport(handle)).fetch_window(
        1, date(2026, 11, 7)
    )
    assert index.coverage.weeks_fetched == 1
    assert index.pages[0].url == mirror_url(44)


def test_events_for_builds_lapse_and_reinstated_events(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PAGE_2026)

    index: OgIndex = indexer(tmp_path, httpx.MockTransport(handle)).fetch_window(
        1, date(2026, 11, 7)
    )
    events: list[StatusEvent] = index.events_for("US-8646606")
    assert [(e.event_type, e.event_date) for e in events] == [("reinstated", date(2026, 10, 7))]
    lapse: StatusEvent = index.events_for("US-8826466")[0]
    assert (lapse.event_type, lapse.effective_date) == ("lapse", date(2026, 9, 9))
    assert lapse.event_date == date(2026, 11, 3)
    assert "US-8826466" in index.expirations()
    assert len(index.evidence_for("US-8646606")) == 1
