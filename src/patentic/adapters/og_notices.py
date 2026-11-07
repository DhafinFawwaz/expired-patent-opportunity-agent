import html
import re
from collections.abc import Collection
from datetime import date, datetime, timedelta
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from patentic.adapters.base import EvidenceRecord, make_evidence_id, sha256_text
from patentic.adapters.http import FetchResult, HttpSource
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import StatusEvent
from patentic.domain.identifiers import (
    IdentifierError,
    PatentId,
    parse_application_number,
    parse_patent_number,
)

PARSER_VERSION: Final[str] = "og-1"
MIRROR_WEEKS: Final[int] = 52
_EXPIRED_TITLE: Final[str] = "Notice of Expiration of Patents Due to Failure to Pay Maintenance Fee"
_REINSTATED_TITLE: Final[str] = "Patents Reinstated Due to the Acceptance of a Late Maintenance Fee"
_TOC_LINK: Final[re.Pattern[str]] = re.compile(r'href="#(ref\d+)">\s*([^<]+)')
_ISSUE_DATE: Final[re.Pattern[str]] = re.compile(
    r"Top of Notices</a>(?:&nbsp;|\s)*([A-Z][a-z]+ \d{1,2}, \d{4})"
)
_CITATION: Final[re.Pattern[str]] = re.compile(r"(\d+ OG \d+)")
_PRE: Final[re.Pattern[str]] = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
_EXPIRED_ON: Final[re.Pattern[str]] = re.compile(
    r"PATENTS WHICH EXPIRED ON ([A-Z][a-z]+ \d{1,2}, \d{4})"
)
_NUMBER: Final[str] = r"((?:RE\.?\s*)?[\d,]{5,})"
_DATE: Final[str] = r"(\d{2}/\d{2}/\d{2,4})"
_EXPIRED_ROW: Final[re.Pattern[str]] = re.compile(
    rf"^\s*{_NUMBER}\s+(\d{{2}}/[\d,]+)\s+{_DATE}\s*$"
)
_REINSTATED_ROW: Final[re.Pattern[str]] = re.compile(
    rf"^\s*{_NUMBER}\s+(\d{{2}}/[\d,]+)\s+{_DATE}\s+{_DATE}\s+{_DATE}\s*$"
)

RowKind = Literal["expired", "reinstated"]


class OgRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    patent: PatentId
    application: str
    issue_date: date
    kind: RowKind
    expired_on: date | None = None
    filing_date: date | None = None
    granted_on: date | None = None
    evidence_id: str
    line: str
    anchor: str


class OgPage(BaseModel):
    url: str
    issue_date: date
    citation: str
    retrieved_at: datetime
    from_cache: bool = False
    rows: list[OgRow]
    sections_found: list[RowKind]

    def evidence_for(self, row: OgRow) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=row.evidence_id,
            source="og_notice",
            url=f"{self.url}#{row.anchor}",
            retrieved_at=self.retrieved_at,
            from_cache=self.from_cache,
            http_status=200,
            raw_snippet=f"{self.citation} ({self.issue_date}): {row.line.strip()}",
            content_sha256=sha256_text(row.line),
            parser_version=PARSER_VERSION,
            patent_key=row.patent.key,
            event_type="lapse" if row.kind == "expired" else "reinstated",
            event_date=row.expired_on if row.kind == "expired" else row.granted_on,
            source_grade="A",
            credibility=2,
        )


def _parse_date(text: str) -> date:
    fmt: str = "%m/%d/%y" if len(text) == len("01/02/03") else "%m/%d/%Y"
    return datetime.strptime(text, fmt).date()  # noqa: DTZ007


def _parse_long_date(text: str) -> date:
    return datetime.strptime(text, "%B %d, %Y").date()  # noqa: DTZ007


def _section(page: str, anchor: str) -> str:
    start: int = page.find(f'name="{anchor}"')
    if start < 0:
        return ""
    end: int = page.find('name="ref', start + len(anchor) + 6)
    return page[start : end if end > 0 else len(page)]


def _section_text(section: str) -> str:
    return html.unescape("\n".join(_PRE.findall(section)))


def parse_toc(
    page: str,
    url: str,
    retrieved_at: datetime,
    keep: Collection[str] | None = None,
    *,
    from_cache: bool = False,
) -> OgPage:
    anchors: dict[RowKind, str] = {}
    for anchor, title in _TOC_LINK.findall(page):
        if title.strip().startswith(_EXPIRED_TITLE):
            anchors.setdefault("expired", anchor)
        elif title.strip().startswith(_REINSTATED_TITLE):
            anchors.setdefault("reinstated", anchor)
    issue_match: re.Match[str] | None = _ISSUE_DATE.search(page)
    if issue_match is None:
        msg = f"no issue date on Gazette page {url}"
        raise ValueError(msg)
    issue_date: date = _parse_long_date(issue_match[1])
    rows: list[OgRow] = []
    citation: str = ""
    for kind, anchor in anchors.items():
        section: str = _section(page, anchor)
        if not citation and (found := _CITATION.search(section)):
            citation = found[1]
        rows.extend(_parse_rows(kind, _section_text(section), url, anchor, retrieved_at, keep))
    return OgPage(
        url=url,
        issue_date=issue_date,
        citation=citation,
        retrieved_at=retrieved_at,
        from_cache=from_cache,
        rows=rows,
        sections_found=list(anchors),
    )


def _parse_rows(
    kind: RowKind,
    text: str,
    url: str,
    anchor: str,
    retrieved_at: datetime,
    keep: Collection[str] | None,
) -> list[OgRow]:
    rows: list[OgRow] = []
    expired_on: date | None = None
    for line in text.split("\n"):
        if header := _EXPIRED_ON.search(line):
            expired_on = _parse_long_date(header[1])
            continue
        pattern: re.Pattern[str] = _EXPIRED_ROW if kind == "expired" else _REINSTATED_ROW
        match: re.Match[str] | None = pattern.match(line)
        if match is None:
            continue
        try:
            patent: PatentId = parse_patent_number(match[1])
            application: str = parse_application_number(match[2])
        except IdentifierError:
            continue
        if kind == "expired" and keep is not None and patent.key not in keep:
            continue
        evidence_id: str = make_evidence_id(
            "og_notice", f"{url}#{anchor}", retrieved_at, line.strip()
        )
        if kind == "expired":
            rows.append(
                OgRow(
                    patent=patent,
                    application=application,
                    issue_date=_parse_date(match[3]),
                    kind=kind,
                    expired_on=expired_on,
                    evidence_id=evidence_id,
                    line=line,
                    anchor=anchor,
                )
            )
        else:
            rows.append(
                OgRow(
                    patent=patent,
                    application=application,
                    filing_date=_parse_date(match[3]),
                    issue_date=_parse_date(match[4]),
                    kind=kind,
                    granted_on=_parse_date(match[5]),
                    evidence_id=evidence_id,
                    line=line,
                    anchor=anchor,
                )
            )
    return rows


def og_week(issue: date) -> tuple[int, int]:
    return issue.year, (issue.timetuple().tm_yday - 1) // 7 + 1


def issue_tuesdays(today: date, weeks: int) -> list[date]:
    latest: date = today - timedelta(days=(today.weekday() - 1) % 7)
    return [latest - timedelta(weeks=i) for i in range(weeks)]


def archive_url(year: int, week: int) -> str:
    return f"https://www.uspto.gov/web/offices/com/sol/og/{year}/week{week:02d}/TOC.htm"


def mirror_url(week: int) -> str:
    return f"https://patentsgazette.uspto.gov/week{week:02d}/OG/TOC.htm"


class OgIndex(BaseModel):
    pages: list[OgPage]
    coverage: ScanCoverage

    def _rows(self, kind: RowKind) -> dict[str, list[tuple[OgPage, OgRow]]]:
        found: dict[str, list[tuple[OgPage, OgRow]]] = {}
        for page in self.pages:
            for row in page.rows:
                if row.kind == kind:
                    found.setdefault(row.patent.key, []).append((page, row))
        return found

    def expirations(self) -> dict[str, list[OgRow]]:
        return {k: [r for _, r in v] for k, v in self._rows("expired").items()}

    def reinstatements(self) -> dict[str, list[OgRow]]:
        return {k: [r for _, r in v] for k, v in self._rows("reinstated").items()}

    def events_for(self, key: str) -> list[StatusEvent]:
        events: list[StatusEvent] = []
        for page, row in self._rows("expired").get(key, []):
            events.append(
                StatusEvent(
                    event_type="lapse",
                    event_date=page.issue_date,
                    effective_date=row.expired_on,
                    source="og_notice",
                    source_code="OG",
                    evidence_id=row.evidence_id,
                )
            )
        for _, row in self._rows("reinstated").get(key, []):
            granted: date = row.granted_on or row.issue_date
            events.append(
                StatusEvent(
                    event_type="reinstated",
                    event_date=granted,
                    source="og_notice",
                    source_code="OG",
                    evidence_id=row.evidence_id,
                )
            )
        return sorted(events, key=lambda e: e.event_date)

    def evidence_for(self, key: str) -> list[EvidenceRecord]:
        return [
            page.evidence_for(row)
            for page in self.pages
            for row in page.rows
            if row.patent.key == key
        ]


class OgIndexer:
    def __init__(self, http: HttpSource) -> None:
        self._http: HttpSource = http

    def fetch_window(self, weeks: int, today: date, keep: Collection[str] | None = None) -> OgIndex:
        pages: list[OgPage] = []
        missing: list[date] = []
        for tuesday in issue_tuesdays(today, weeks):
            page: OgPage | None = self._fetch_week(tuesday, today, keep)
            if page is None:
                missing.append(tuesday)
            else:
                pages.append(page)
        issues: list[date] = [p.issue_date for p in pages]
        coverage: ScanCoverage = ScanCoverage(
            weeks_fetched=len(pages),
            first_issue=min(issues) if issues else None,
            last_issue=max(issues) if issues else None,
            missing_weeks=missing,
            as_of=today,
        )
        return OgIndex(pages=pages, coverage=coverage)

    def _fetch_week(
        self, tuesday: date, today: date, keep: Collection[str] | None
    ) -> OgPage | None:
        year, week = og_week(tuesday)
        urls: list[str] = [archive_url(year, week)]
        if today - tuesday < timedelta(weeks=MIRROR_WEEKS):
            urls.append(mirror_url(week))
        for url in urls:
            result: FetchResult = self._http.get(url)
            if result.status != 200:  # noqa: PLR2004
                continue
            try:
                page: OgPage = parse_toc(
                    result.text, url, result.retrieved_at, keep, from_cache=result.from_cache
                )
            except ValueError:
                continue
            if page.issue_date == tuesday:
                return page
        return None
