from datetime import date

from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import StatusEvent
from patentic.domain.status_rules import StatusAssessment
from patentic.graph.nodes.bundle import _methodology_fallback, timeline_rows
from patentic.report.bundle import TimelineRow

LAPSE: StatusEvent = StatusEvent(
    event_type="lapse",
    event_date=date(2026, 11, 3),
    effective_date=date(2026, 9, 4),
    source="og_notice",
    source_code="EXP.",
    evidence_id="ev-og",
)
COVERAGE: ScanCoverage = ScanCoverage(
    weeks_fetched=104, first_issue=date(2024, 11, 12), last_issue=date(2026, 11, 3)
)


def test_expired_timeline_starts_at_grant_and_ends_with_the_reinstatement_scan() -> None:
    assessment: StatusAssessment = StatusAssessment(
        label="expired_nonpayment", as_of=date(2026, 11, 7), timeline=[LAPSE]
    )
    rows: list[TimelineRow] = timeline_rows(assessment, date(2018, 9, 4), COVERAGE)
    assert [r.date for r in rows] == [date(2018, 9, 4), date(2026, 11, 3), date(2026, 11, 3)]
    assert rows[0].event == "Granted"
    assert rows[0].grade == "A"
    assert rows[2].event == "No reinstatement listed in Gazette issues 2024-11-12 to 2026-11-03"
    assert [r.evidence_id for r in rows] == ["", "ev-og", ""]


def test_reinstated_timeline_has_no_scan_row() -> None:
    revived: StatusEvent = LAPSE.model_copy(
        update={"event_type": "reinstated", "event_date": date(2026, 11, 10), "evidence_id": "r"}
    )
    assessment: StatusAssessment = StatusAssessment(
        label="reinstated", as_of=date(2026, 11, 12), timeline=[LAPSE, revived]
    )
    rows: list[TimelineRow] = timeline_rows(assessment, date(2018, 9, 4), COVERAGE)
    assert len(rows) == 3
    assert rows[-1].evidence_id == "r"


def test_scan_row_names_missing_weeks() -> None:
    gappy: ScanCoverage = COVERAGE.model_copy(update={"missing_weeks": [date(2026, 10, 13)]})
    assessment: StatusAssessment = StatusAssessment(
        label="expired_nonpayment",
        as_of=date(2026, 11, 7),
        effective_date=date(2026, 9, 4),
        timeline=[LAPSE],
    )
    rows: list[TimelineRow] = timeline_rows(assessment, date(2018, 9, 4), gappy)
    assert "No reinstatement listed" not in rows[-1].event
    assert "2026-10-13" in rows[-1].event


def test_methodology_fallback_admits_missing_weeks() -> None:
    gappy: ScanCoverage = COVERAGE.model_copy(update={"missing_weeks": [date(2026, 10, 13)]})
    assert "Every later reinstatement list was scanned" not in _methodology_fallback(8, 104, gappy)
    assert "Every later reinstatement list was scanned" in _methodology_fallback(8, 104, COVERAGE)
