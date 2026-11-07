from datetime import date

from patentic.domain.events import EventType, Source, Stage, StatusEvent
from patentic.domain.identifiers import PatentId, parse_patent_number
from patentic.domain.status_rules import (
    ScanCoverage,
    StatusAssessment,
    anniversaries,
    assess_status,
    due_dates,
)

UTILITY: PatentId = parse_patent_number("9999901")
GRANT: date = date(2014, 9, 9)
FILING: date = date(2011, 5, 2)
FULL_SCAN: ScanCoverage = ScanCoverage(
    weeks_fetched=104, first_issue=date(2024, 11, 5), last_issue=date(2026, 11, 3)
)


def ev(
    event_type: EventType,
    on: date,
    source: Source = "og_notice",
    code: str = "OG",
    effective: date | None = None,
    stage: Stage | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_type=event_type,
        event_date=on,
        effective_date=effective,
        stage=stage,
        source=source,
        source_code=code,
        evidence_id=f"{source}-{code}-{on.isoformat()}",
    )


def assess(
    events: list[StatusEvent],
    today: date,
    patent: PatentId = UTILITY,
    grant: date = GRANT,
    filing: date = FILING,
) -> StatusAssessment:
    return assess_status(patent, grant, filing, events, FULL_SCAN, today)


def test_anniversaries_and_due_dates() -> None:
    assert anniversaries(GRANT) == (date(2018, 9, 9), date(2022, 9, 9), date(2026, 9, 9))
    assert due_dates(GRANT) == (date(2018, 3, 9), date(2022, 3, 9), date(2026, 3, 9))


def test_leap_day_grant_rolls_to_feb_28() -> None:
    assert anniversaries(date(2016, 2, 29))[0] == date(2020, 2, 29)
    assert anniversaries(date(2016, 2, 29))[1] == date(2024, 2, 29)
    assert due_dates(date(2015, 8, 31))[0] == date(2019, 2, 28)


def test_design_patent_not_subject() -> None:
    result: StatusAssessment = assess([], date(2026, 11, 7), patent=parse_patent_number("D812345"))
    assert result.label == "not_subject_to_maintenance_fees"


def test_expired_nonpayment_from_og_row() -> None:
    lapse: StatusEvent = ev("lapse", date(2026, 11, 3), effective=date(2026, 9, 9))
    result: StatusAssessment = assess([lapse], date(2026, 11, 7))
    assert result.label == "expired_nonpayment"
    assert result.effective_date == date(2026, 9, 9)
    assert result.stage == 12
    assert result.evidence_ids == [lapse.evidence_id]


def test_reinstated_after_lapse() -> None:
    events: list[StatusEvent] = [
        ev("lapse", date(2022, 11, 1), effective=date(2022, 9, 9)),
        ev("reinstated", date(2023, 2, 14)),
    ]
    result: StatusAssessment = assess(events, date(2023, 6, 1))
    assert result.label == "reinstated"
    assert any("intervening rights" in note.lower() for note in result.notes)


def test_grace_period_includes_anniversary_day() -> None:
    reminder: StatusEvent = ev("reminder", date(2018, 4, 20), source="ops", code="REMI")
    result: StatusAssessment = assess([reminder], date(2018, 9, 9))
    assert result.label == "in_grace_period"
    assert result.effective_date == date(2018, 9, 9)
    assert result.stage == 4


def test_day_after_anniversary_is_not_grace() -> None:
    reminder: StatusEvent = ev("reminder", date(2018, 4, 20), source="ops", code="REMI")
    result: StatusAssessment = assess([reminder], date(2018, 9, 10))
    assert result.label != "in_grace_period"


def test_petition_pending() -> None:
    events: list[StatusEvent] = [
        ev("lapse", date(2022, 11, 1), effective=date(2022, 9, 9)),
        ev("petition_filed", date(2023, 1, 10), source="odp", code="PMFP"),
    ]
    assert assess(events, date(2023, 2, 1)).label == "petition_pending"


def test_conflicting_without_resolving_notice() -> None:
    events: list[StatusEvent] = [
        ev("lapse", date(2022, 10, 3), source="ops", code="LAPS", effective=date(2022, 9, 9)),
        ev("fee_paid", date(2022, 12, 1), source="ops", code="MAFP", stage=8),
    ]
    assert assess(events, date(2023, 2, 1)).label == "conflicting"


def test_later_secondary_revival_against_official_lapse_is_conflicting() -> None:
    events: list[StatusEvent] = [
        ev("lapse", date(2022, 11, 1), effective=date(2022, 9, 9)),
        ev("reinstated", date(2023, 1, 9), source="ops", code="PRDP"),
    ]
    assert assess(events, date(2023, 2, 1)).label == "conflicting"


def test_later_official_notice_wins() -> None:
    events: list[StatusEvent] = [
        ev("lapse", date(2026, 3, 16), source="ops", code="LAPS"),
        ev("reinstated", date(2026, 10, 7)),
    ]
    result: StatusAssessment = assess(events, date(2026, 11, 7))
    assert result.label == "reinstated"
    assert any("og_notice dated later than ops" in note for note in result.notes)


def test_second_lapse_after_reinstatement_is_expired() -> None:
    events: list[StatusEvent] = [
        ev("lapse", date(2018, 11, 6), effective=date(2018, 9, 9)),
        ev("reinstated", date(2019, 1, 8)),
        ev("lapse", date(2022, 11, 1), effective=date(2022, 9, 9)),
    ]
    result: StatusAssessment = assess(events, date(2023, 1, 1))
    assert result.label == "expired_nonpayment"
    assert result.stage == 8


def test_expired_end_of_term() -> None:
    result: StatusAssessment = assess(
        [], date(2026, 11, 7), grant=date(2006, 3, 7), filing=date(2004, 3, 1)
    )
    assert result.label == "expired_end_of_term"
    assert result.effective_date == date(2024, 3, 1)
    assert any("PTA unknown" in note for note in result.notes)


def test_in_force_with_payments() -> None:
    events: list[StatusEvent] = [
        ev("fee_paid", date(2018, 1, 5), source="ops", code="FPAY", stage=4),
        ev("fee_paid", date(2022, 1, 5), source="ops", code="MAFP", stage=8),
    ]
    assert assess(events, date(2024, 1, 1)).label == "in_force"


def test_no_events_after_first_due_date_is_unknown() -> None:
    assert assess([], date(2024, 1, 1)).label == "unknown"


def test_duplicate_events_deduplicated() -> None:
    lapse: StatusEvent = ev("lapse", date(2026, 11, 3), effective=date(2026, 9, 9))
    result: StatusAssessment = assess([lapse, lapse.model_copy()], date(2026, 11, 7))
    assert len(result.timeline) == 1


def test_8646606_recorded_sequence() -> None:
    patent: PatentId = parse_patent_number("8,646,606")
    events: list[StatusEvent] = [
        ev("fee_paid", date(2017, 4, 12), source="ops", code="FPAY", stage=4),
        ev("fee_paid", date(2021, 8, 11), source="ops", code="MAFP", stage=8),
        ev("reminder", date(2025, 9, 29), source="ops", code="FEPP"),
        ev("lapse", date(2026, 3, 16), source="ops", code="LAPS"),
        ev("lapse", date(2026, 3, 16), source="ops", code="STCH"),
        ev("lapse", date(2026, 4, 7), source="ops", code="FP", effective=date(2026, 2, 11)),
        ev("reinstated", date(2026, 10, 7)),
    ]
    result: StatusAssessment = assess_status(
        patent, date(2014, 2, 11), date(2011, 2, 18), events, FULL_SCAN, date(2026, 11, 7)
    )
    assert result.label == "reinstated"
    assert result.effective_date == date(2026, 2, 11)
    assert result.stage == 12
    assert [e.source_code for e in result.timeline][-1] == "OG"
