from datetime import date

import pytest

from patentic.domain.confidence import (
    Confidence,
    compute_confidence,
    credibility_for,
    grade_for_source,
)
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import EventType, Source, StatusEvent
from patentic.domain.identifiers import parse_patent_number
from patentic.domain.status_rules import StatusAssessment, assess_status

EXPIRY: date = date(2026, 9, 9)
FULL: ScanCoverage = ScanCoverage(
    weeks_fetched=104, last_issue=date(2026, 11, 3), as_of=date(2026, 11, 7)
)
SHORT: ScanCoverage = ScanCoverage(
    weeks_fetched=104, last_issue=date(2026, 9, 22), as_of=date(2026, 11, 7)
)


def ev(event_type: EventType, source: Source, on: date = date(2026, 11, 3)) -> StatusEvent:
    return StatusEvent(
        event_type=event_type,
        event_date=on,
        effective_date=EXPIRY if event_type == "lapse" else None,
        source=source,
        source_code="X",
        evidence_id=f"{source}-{event_type}",
    )


def test_official_with_complete_scan_is_high() -> None:
    result: Confidence = compute_confidence(
        "expired_nonpayment", [ev("lapse", "og_notice")], FULL, EXPIRY
    )
    assert result == "high"


def test_official_plus_agreeing_source_is_very_high() -> None:
    events: list[StatusEvent] = [ev("lapse", "og_notice"), ev("lapse", "ops", date(2026, 9, 28))]
    assert compute_confidence("expired_nonpayment", events, FULL, EXPIRY) == "very_high"


def test_incomplete_scan_caps_at_medium() -> None:
    events: list[StatusEvent] = [ev("lapse", "og_notice"), ev("lapse", "ops")]
    assert compute_confidence("expired_nonpayment", events, SHORT, EXPIRY) == "medium"


def test_secondary_source_only_is_medium() -> None:
    assert compute_confidence("expired_nonpayment", [ev("lapse", "ops")], FULL, EXPIRY) == "medium"


def test_conflicting_is_low() -> None:
    events: list[StatusEvent] = [ev("lapse", "og_notice"), ev("reinstated", "ops")]
    assert compute_confidence("conflicting", events, FULL, EXPIRY) == "low"


@pytest.mark.parametrize("label", ["expired_end_of_term", "unknown"])
def test_inferred_labels_are_very_low(label: str) -> None:
    assert compute_confidence(label, [], FULL, None) == "very_low"


def test_official_reinstatement_is_high_even_when_ops_lags() -> None:
    events: list[StatusEvent] = [
        ev("lapse", "ops", date(2026, 3, 16)),
        ev("reinstated", "og_notice"),
    ]
    assert compute_confidence("reinstated", events, FULL, EXPIRY) == "high"


def test_source_grades() -> None:
    assert grade_for_source("og_notice", "status") == "A"
    assert grade_for_source("ops", "status") == "B"
    assert grade_for_source("bigquery", "bibliographic") == "A"
    assert grade_for_source("bigquery", "status") == "F"
    assert grade_for_source("fixture", "status") == "F"


def test_credibility() -> None:
    assert credibility_for(2, official=True) == 1
    assert credibility_for(1, official=True) == 2
    assert credibility_for(1, official=False) == 3
    assert credibility_for(0, official=False) == 6


def test_assess_status_fills_confidence() -> None:
    patent = parse_patent_number("9999901")
    lapse: StatusEvent = ev("lapse", "og_notice")
    grant: date = date(2014, 9, 9)
    filing: date = date(2011, 5, 2)
    today: date = date(2026, 11, 7)
    high: StatusAssessment = assess_status(patent, grant, filing, [lapse], FULL, today)
    assert high.confidence == "high"
    both: StatusAssessment = assess_status(
        patent, grant, filing, [lapse, ev("lapse", "ops", date(2026, 9, 28))], FULL, today
    )
    assert both.confidence == "very_high"
    short: StatusAssessment = assess_status(patent, grant, filing, [lapse], SHORT, today)
    assert short.confidence == "medium"


def test_missing_week_after_expiry_breaks_coverage() -> None:
    gap: ScanCoverage = ScanCoverage(
        weeks_fetched=103,
        last_issue=date(2026, 11, 3),
        missing_weeks=[date(2026, 10, 13)],
        as_of=date(2026, 11, 7),
    )
    assert not gap.covers_after(EXPIRY)
    assert gap.covers_after(date(2026, 10, 20))
