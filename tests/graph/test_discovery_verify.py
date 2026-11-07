from collections.abc import Collection, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from patentic.adapters.base import ClaimRecord, PatentRecord
from patentic.adapters.bigquery import BigQueryGateway, BytesLedger, Continuity
from patentic.adapters.fixtures import FixtureCase, load_fixtures
from patentic.adapters.og_notices import OgIndex, OgIndexer, parse_toc
from patentic.domain.coverage import ScanCoverage
from patentic.domain.identifiers import parse_patent_number
from patentic.domain.scoring import ScoringWeights
from patentic.graph.deps import Deps
from patentic.graph.nodes.discover import grant_window_for
from patentic.graph.nodes.normalise import screen_record
from patentic.graph.state import Candidate
from tests.graph.helpers import REQUEST, TODAY, compile_graph, make_deps, run_until_interrupt

ROOT: Path = Path(__file__).parents[2]
CONFIG: RunnableConfig = {"configurable": {"thread_id": "t1"}}
PAGE: str = (ROOT / "tests" / "data" / "og" / "2026-week44-excerpt.html").read_text()


def record(number: str, cpc: list[str], grant: date = date(2014, 9, 9)) -> PatentRecord:
    return PatentRecord(
        patent=parse_patent_number(number),
        title=f"Cleaning tool {number}",
        grant_date=grant,
        filing_date=date(2012, 3, 1),
        kind="B2",
        num_claims=2,
        cpc_codes=cpc,
    )


class FakeOg(OgIndexer):
    def __init__(self, *, empty: bool = False) -> None:
        self.empty: bool = empty
        self.keep: Collection[str] | None = None

    def fetch_window(self, weeks: int, today: date, keep: Collection[str] | None = None) -> OgIndex:
        self.keep = keep
        if self.empty:
            return OgIndex(pages=[], coverage=ScanCoverage(weeks_fetched=0, as_of=today))
        page = parse_toc(
            PAGE, "https://og/2026/week44/TOC.htm", datetime(2026, 11, 7, tzinfo=UTC), keep
        )
        coverage = ScanCoverage(
            weeks_fetched=1, first_issue=page.issue_date, last_issue=page.issue_date, as_of=today
        )
        return OgIndex(pages=[page], coverage=coverage)


class FakeBq(BigQueryGateway):
    def __init__(self, tmp_path: Path, records: list[PatentRecord]) -> None:
        super().__init__(None, tmp_path, BytesLedger(tmp_path / "l.json"), offline=True)
        self.records: list[PatentRecord] = records

    def discover(
        self, cpc_prefixes: Sequence[str], grant_from: date, grant_to: date
    ) -> list[PatentRecord]:
        return self.records

    def claims(self, keys: Sequence[str]) -> dict[str, list[ClaimRecord]]:
        return {
            k: [ClaimRecord(patent_key=k, sequence=1, text="A mop comprising a pad on a frame.")]
            for k in keys
        }

    def continuity(self, keys: Sequence[str]) -> dict[str, Continuity]:
        return {k: Continuity(terminal_disclaimer=False) for k in keys}

    def forward_citations(self, keys: Sequence[str]) -> dict[str, list[str]]:
        return {}


def approve_and_run(deps: Deps) -> dict[str, Any]:
    graph = compile_graph(deps)
    run_until_interrupt(graph, {"request": REQUEST})
    run_until_interrupt(graph, Command(resume={"action": "approve"}))
    values: dict[str, Any] = graph.get_state(CONFIG).values
    return values


def test_grant_window_covers_all_three_fee_stages() -> None:
    assert grant_window_for(date(2024, 11, 12), date(2026, 11, 3)) == (
        date(2012, 11, 12),
        date(2022, 11, 3),
    )


def test_discover_intersects_og_and_cpc(tmp_path: Path) -> None:
    og: FakeOg = FakeOg()
    bq: FakeBq = FakeBq(
        tmp_path, [record("8826466", ["A47L13/20"]), record("7000001", ["A47L13/20"])]
    )
    values: dict[str, Any] = approve_and_run(make_deps(tmp_path, og=og, bq=bq))
    assert set(values["candidates"]) == {"US-8826466"}
    assert og.keep == {"US-8826466", "US-7000001"}
    candidate: Candidate = values["candidates"]["US-8826466"]
    assert candidate.assessment is not None
    assert candidate.assessment.label == "expired_nonpayment"
    assert candidate.assessment.effective_date == date(2026, 9, 9)
    assert values["evidence"]


def test_tier1_reject_excluded_from_pool(tmp_path: Path) -> None:
    bq: FakeBq = FakeBq(tmp_path, [record("8826466", ["A47L13/20", "A47L9/2805"])])
    values: dict[str, Any] = approve_and_run(make_deps(tmp_path, og=FakeOg(), bq=bq))
    candidate: Candidate = values["candidates"]["US-8826466"]
    assert not candidate.screening.passed
    assert candidate.recommendation == "Exclude"
    assert values["pool"] == []


def test_normalise_rejects_design_patent(tmp_path: Path) -> None:
    deps: Deps = make_deps(tmp_path)
    candidate: Candidate = screen_record(record("D812345", ["A47L13/20"]), [], deps)
    assert candidate.assessment is not None
    assert candidate.assessment.label == "not_subject_to_maintenance_fees"
    assert not candidate.screening.passed


def test_verify_fanout_assesses_every_fixture(tmp_path: Path) -> None:
    fixtures: list[FixtureCase] = load_fixtures(ROOT / "fixtures" / "synthetic")
    deps: Deps = make_deps(tmp_path)
    deps = Deps(**{**deps.__dict__, "fixtures": tuple(fixtures), "today": fixtures[0].today})
    values: dict[str, Any] = approve_and_run(deps)
    for case in fixtures:
        candidate: Candidate = values["candidates"][case.record.patent.key]
        assert candidate.assessment is not None
        assert (candidate.assessment.label, candidate.assessment.confidence) == (
            case.expected.label,
            case.expected.confidence,
        ), case.name
        assert candidate.is_synthetic
    assert values["candidates"]["US-9999906"].flags == ["related_active_continuation"]


def test_rank_pool_limits_to_configured_size(tmp_path: Path) -> None:
    fixtures: list[FixtureCase] = load_fixtures(ROOT / "fixtures" / "synthetic")
    deps: Deps = make_deps(tmp_path)
    deps = Deps(
        **{
            **deps.__dict__,
            "fixtures": tuple(fixtures),
            "today": TODAY,
            "weights": ScoringWeights(analysis_pool=1),
        }
    )
    values: dict[str, Any] = approve_and_run(deps)
    assert len(values["pool"]) == 1
    statuses: dict[str, str | None] = {k: c.recommendation for k, c in values["candidates"].items()}
    assert list(statuses.values()).count("NotAnalysed") == 1


def test_source_outage_recorded_and_run_continues(tmp_path: Path) -> None:
    bq: FakeBq = FakeBq(tmp_path, [record("8826466", ["A47L13/20"])])
    values: dict[str, Any] = approve_and_run(make_deps(tmp_path, og=FakeOg(empty=True), bq=bq))
    assert values["outages"] == ["og_notice"]
    assert values["candidates"] == {}
    assert values["stage"] == "rank"
