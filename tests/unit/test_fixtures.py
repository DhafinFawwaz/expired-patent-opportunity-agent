from datetime import UTC, datetime
from pathlib import Path

import pytest

from patentic.adapters.base import ClaimRecord, EvidenceRecord, independent_claims, make_evidence_id
from patentic.adapters.fixtures import FixtureCase, load_fixtures
from patentic.domain.status_rules import StatusAssessment, assess_status

FIXTURES: Path = Path(__file__).parents[2] / "fixtures" / "synthetic"


def test_fixtures_load_and_validate() -> None:
    cases: list[FixtureCase] = load_fixtures(FIXTURES)
    assert [c.record.patent.key for c in cases] == [f"US-999990{i}" for i in range(1, 7)]
    assert all(e.is_synthetic for c in cases for e in c.evidence)
    assert all(
        e.evidence_id in {r.evidence_id for r in c.evidence} for c in cases for e in c.events
    )


@pytest.mark.parametrize("case", load_fixtures(FIXTURES), ids=lambda c: c.name)
def test_fixture_expectations_hold(case: FixtureCase) -> None:
    result: StatusAssessment = assess_status(
        case.record.patent,
        case.record.grant_date,
        case.record.filing_date,
        case.events,
        case.coverage,
        case.today,
    )
    assert (result.label, result.confidence) == (case.expected.label, case.expected.confidence)


def test_related_fixture_has_continuation() -> None:
    related: FixtureCase = load_fixtures(FIXTURES)[5]
    assert related.record.children == ["US-9999916"]
    assert related.related[0].patent.key == "US-9999916"
    assert related.expected.flags == ["related_active_continuation"]


def test_evidence_id_is_deterministic() -> None:
    at: datetime = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)
    first: str = make_evidence_id("og_notice", "https://x/TOC.htm#ref2", at, "8,646,606 ...")
    second: str = make_evidence_id("og_notice", "https://x/TOC.htm#ref2", at, "8,646,606 ...")
    assert first == second
    assert len(first) == 12


def test_snippet_truncated_to_2000() -> None:
    record: EvidenceRecord = EvidenceRecord(
        evidence_id="abc",
        source="og_notice",
        url="https://x",
        retrieved_at=datetime(2026, 11, 7, tzinfo=UTC),
        http_status=200,
        raw_snippet="x" * 5000,
        content_sha256="0" * 64,
        parser_version="og-1",
        source_grade="A",
        credibility=2,
    )
    assert len(record.raw_snippet) == 2000


def test_independent_claims() -> None:
    claims: list[ClaimRecord] = [
        ClaimRecord(patent_key="US-1", sequence=1, text="A mop.", dependent_on=None),
        ClaimRecord(patent_key="US-1", sequence=2, text="The mop of claim 1.", dependent_on=1),
        ClaimRecord(patent_key="US-1", sequence=3, text="A method.", dependent_on=None),
    ]
    assert [c.sequence for c in independent_claims(claims)] == [1, 3]
