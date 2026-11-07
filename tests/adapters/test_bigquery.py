from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from patentic.adapters.base import ClaimRecord, PatentRecord
from patentic.adapters.bigquery import (
    BigQueryBudgetError,
    BigQueryGateway,
    BytesLedger,
    CacheMissError,
    Continuity,
    parse_dependent,
)


class FakeRunner:
    def __init__(self, rows: list[dict[str, object]], dry_bytes: int = 1_000_000) -> None:
        self.rows: list[dict[str, object]] = rows
        self.dry_bytes: int = dry_bytes
        self.runs: list[str] = []

    def dry_run(self, sql: str, params: Mapping[str, object]) -> int:
        return self.dry_bytes

    def run(
        self, sql: str, params: Mapping[str, object], max_bytes: int
    ) -> tuple[list[dict[str, object]], int]:
        self.runs.append(sql)
        return self.rows, self.dry_bytes


def gateway(tmp_path: Path, runner: FakeRunner | None, *, offline: bool = False) -> BigQueryGateway:
    return BigQueryGateway(
        runner=runner,
        cache_dir=tmp_path / "bq",
        ledger=BytesLedger(tmp_path / "ledger.json"),
        offline=offline,
    )


def test_query_dry_runs_then_runs_and_caches(tmp_path: Path) -> None:
    runner: FakeRunner = FakeRunner([{"a": 1}], dry_bytes=5_000)
    gw: BigQueryGateway = gateway(tmp_path, runner)
    assert gw.query("SELECT 1", {"x": "y"}, "probe") == [{"a": 1}]
    assert gw.query("SELECT 1", {"x": "y"}, "probe") == [{"a": 1}]
    assert len(runner.runs) == 1
    assert gw.ledger.total() == 5_000


def test_query_refuses_over_budget(tmp_path: Path) -> None:
    runner: FakeRunner = FakeRunner([], dry_bytes=60_000_000_000)
    with pytest.raises(BigQueryBudgetError):
        gateway(tmp_path, runner).query("SELECT big", {}, "big")
    assert runner.runs == []


def test_offline_cache_miss_raises(tmp_path: Path) -> None:
    with pytest.raises(CacheMissError):
        gateway(tmp_path, None, offline=True).query("SELECT 1", {}, "probe")


def test_offline_cache_hit_works(tmp_path: Path) -> None:
    gateway(tmp_path, FakeRunner([{"a": 2}])).query("SELECT 2", {}, "p")
    assert gateway(tmp_path, None, offline=True).query("SELECT 2", {}, "p") == [{"a": 2}]


def test_discover_maps_rows_to_patent_records(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [
        {
            "id": "9032584",
            "kind": "B1",
            "date": "2015-05-19",
            "title": "Handheld cleaning tool kit",
            "num_claims": 12,
            "cpc": ["A47L13/16", "A47L13/51"],
            "filing_date": "2014-01-28",
            "assignees": ["Acme Housewares"],
        }
    ]
    records: list[PatentRecord] = gateway(tmp_path, FakeRunner(rows)).discover(
        ["A47L13/"], date(2014, 1, 1), date(2015, 12, 31)
    )
    record: PatentRecord = records[0]
    assert record.patent.key == "US-9032584"
    assert record.patent.kind == "B1"
    assert record.grant_date == date(2015, 5, 19)
    assert record.filing_date == date(2014, 1, 28)
    assert record.cpc_codes == ["A47L13/16", "A47L13/51"]
    assert record.entity_status == "unknown"


def test_claims_groups_by_patent_and_marks_dependents(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [
        {
            "patent_id": "9032584",
            "sequence": "2",
            "dependent": "claim 1",
            "text": "2. The kit of claim 1.",
        },
        {"patent_id": "9032584", "sequence": "1", "dependent": None, "text": "1. A cleaning kit."},
    ]
    claims: dict[str, list[ClaimRecord]] = gateway(tmp_path, FakeRunner(rows)).claims(
        ["US-9032584"]
    )
    assert [(c.sequence, c.dependent_on) for c in claims["US-9032584"]] == [(1, None), (2, 1)]


@pytest.mark.parametrize(
    ("value", "text", "expected"),
    [
        (None, "1. A mop.", None),
        ("-1", "1. A mop.", None),
        ("claim 3", "4. The mop of claim 3.", 3),
        ("2", "3. The mop.", 2),
        (None, "5. The mop according to claim 4, wherein", 4),
    ],
)
def test_parse_dependent(value: str | None, text: str, expected: int | None) -> None:
    assert parse_dependent(value, text) == expected


def test_forward_citations_grouped(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [
        {"citation_id": "9032584", "patent_id": "10500001"},
        {"citation_id": "9032584", "patent_id": "10600002"},
    ]
    cites: dict[str, list[str]] = gateway(tmp_path, FakeRunner(rows)).forward_citations(
        ["US-9032584"]
    )
    assert cites == {"US-9032584": ["US-10500001", "US-10600002"]}


def test_continuity_types_and_disclaimer(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [
        {
            "patent_id": "9032584",
            "doctype": "continuation",
            "relkind": "child-doc",
            "reldocno": "14712345",
            "term_disclaimer": None,
        },
        {
            "patent_id": "9032584",
            "doctype": "division",
            "relkind": "parent-grant-document",
            "reldocno": "8123456",
            "term_disclaimer": "This patent is subject to a terminal disclaimer.",
        },
    ]
    info: dict[str, Continuity] = gateway(tmp_path, FakeRunner(rows)).continuity(["US-9032584"])
    entry: Continuity = info["US-9032584"]
    assert entry.children == {"application 14712345": "continuation"}
    assert entry.parents == {"US-8123456": "division"}
    assert entry.terminal_disclaimer is True


def test_claims_are_cached_per_patent_and_prefetched(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [
        {"patent_id": "1", "sequence": 1, "text": "1. A mop.", "dependent": None},
        {"patent_id": "2", "sequence": 1, "text": "1. A brush.", "dependent": None},
    ]
    runner: FakeRunner = FakeRunner(rows)
    gw: BigQueryGateway = gateway(tmp_path, runner)
    first: dict[str, list[ClaimRecord]] = gw.claims(["US-1"], prefetch=["US-1", "US-2", "US-3"])
    assert list(first) == ["US-1"]
    later: dict[str, list[ClaimRecord]] = gw.claims(["US-2", "US-3"])
    assert [c.text for c in later["US-2"]] == ["1. A brush."]
    assert later.get("US-3", []) == []
    assert len(runner.runs) == 1


def test_discovery_window_is_widened_to_whole_years(tmp_path: Path) -> None:
    def row(patent_id: str, granted: str) -> dict[str, object]:
        return {
            "id": patent_id,
            "kind": "B2",
            "date": granted,
            "title": "Mop",
            "cpc": ["A47L13/20"],
        }

    runner: FakeRunner = FakeRunner(
        [row("1", "2014-01-05"), row("2", "2014-06-01"), row("3", "2022-12-30")]
    )
    gw: BigQueryGateway = gateway(tmp_path, runner)
    monday: list[PatentRecord] = gw.discover(["A47L13/"], date(2014, 3, 1), date(2022, 11, 7))
    tuesday: list[PatentRecord] = gw.discover(["A47L13/"], date(2014, 3, 2), date(2022, 11, 8))
    assert [r.patent.key for r in monday] == ["US-2"]
    assert [r.patent.key for r in tuesday] == ["US-2"]
    assert len(runner.runs) == 1
