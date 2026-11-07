from datetime import date
from pathlib import Path

from patentic.adapters.odp_maintfee import (
    MaintFeeLine,
    OdpMaintFeeSource,
    parse_maintfee_line,
    to_events,
)
from patentic.domain.events import StatusEvent

LINES: list[str] = (
    (Path(__file__).parents[1] / "data" / "odp" / "maintfee-sample.txt").read_text().splitlines()
)


def test_parse_line_columns() -> None:
    parsed: MaintFeeLine = parse_maintfee_line(LINES[0])
    assert parsed.patent.key == "US-9999901"
    assert parsed.application == "15207111"
    assert parsed.entity == "Y"
    assert (parsed.filing_date, parsed.grant_date) == (date(2016, 7, 12), date(2018, 3, 6))
    assert (parsed.event_date, parsed.code) == (date(2021, 8, 12), "M2551")


def test_reissue_line() -> None:
    assert parse_maintfee_line(LINES[10]).patent.key == "US-RE46721"


def test_all_sample_lines_parse() -> None:
    assert len([parse_maintfee_line(line) for line in LINES]) == 50


def test_exp_then_expx_yields_lapse_and_reinstated() -> None:
    events: list[StatusEvent] = to_events([parse_maintfee_line(line) for line in LINES[3:10]])
    kinds: list[str] = [e.event_type for e in events]
    assert kinds[0] == "fee_paid"
    assert events[0].stage == 8
    assert "lapse" in kinds
    assert kinds[-1] == "reinstated"
    assert all(e.source == "odp" for e in events)


def test_duplicate_exp_rows_deduplicated() -> None:
    events: list[StatusEvent] = to_events([parse_maintfee_line(line) for line in LINES[3:10]])
    assert sum(1 for e in events if e.event_type == "lapse") == 1


def test_source_disabled_without_key() -> None:
    assert not OdpMaintFeeSource(None).enabled
    assert OdpMaintFeeSource("k").enabled
