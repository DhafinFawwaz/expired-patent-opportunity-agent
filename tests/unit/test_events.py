from datetime import date

import pytest

from patentic.domain.events import (
    EventType,
    StatusEvent,
    map_inpadoc_code,
    map_peds_code,
    map_usptofile_code,
    stage_from_code,
)


@pytest.mark.parametrize(
    ("code", "text", "expected"),
    [
        ("LAPS", "", "lapse"),
        ("STCH", "", "lapse"),
        ("FP", "", "lapse"),
        ("PRDP", "", "reinstated"),
        ("REIN", "", "reinstated"),
        ("STCK", "", "reinstated"),
        ("FPAY", "", "fee_paid"),
        ("MAFP", "", "fee_paid"),
        ("REMI", "", "reminder"),
        ("FEPP", "Maintenance fee reminder mailed", "reminder"),
        ("FEPP", "Entity status set to undiscounted", None),
        ("SULP", "", "surcharge"),
        ("DC", "", "terminal_disclaimer"),
        ("EXPY", "", None),
    ],
)
def test_inpadoc_codes(code: str, text: str, expected: EventType | None) -> None:
    assert map_inpadoc_code(code, text) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("EXP.", "lapse"),
        ("EXPX", "reinstated"),
        ("M1551", "fee_paid"),
        ("M2552", "fee_paid"),
        ("M3553", "fee_paid"),
        ("M1554", "surcharge"),
        ("REM.", "reminder"),
        ("PMFP", "petition_filed"),
        ("PMFG", "petition_granted"),
        ("PMFD", "petition_denied"),
        ("F165", "defective_payment"),
        ("XXXX", None),
    ],
)
def test_usptofile_codes(code: str, expected: EventType | None) -> None:
    assert map_usptofile_code(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("REIN", "reinstated"),
        ("EXP.", "lapse"),
        ("DIST", "terminal_disclaimer"),
        ("M1551", "fee_paid"),
    ],
)
def test_peds_codes(code: str, expected: EventType) -> None:
    assert map_peds_code(code) == expected


@pytest.mark.parametrize(
    ("code", "stage"), [("M1551", 4), ("M2552", 8), ("M3553", 12), ("EXP.", None)]
)
def test_stage_from_code(code: str, stage: int | None) -> None:
    assert stage_from_code(code) == stage


def test_status_event_is_frozen_and_hashable() -> None:
    event: StatusEvent = StatusEvent(
        event_type="lapse",
        event_date=date(2026, 3, 16),
        source="ops",
        source_code="LAPS",
        evidence_id="abc123def456",
    )
    assert hash(event) == hash(event.model_copy())
    with pytest.raises(ValueError, match="frozen"):
        event.event_type = "reinstated"  # type: ignore[misc]
