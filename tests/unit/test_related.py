from datetime import date

from patentic.adapters.base import PatentRecord
from patentic.domain.identifiers import parse_patent_number
from patentic.domain.related import RelatedRecord, related_flags, related_records


def make(children: list[str], td: bool | None = None) -> PatentRecord:
    return PatentRecord(
        patent=parse_patent_number("9999906"),
        title="Toilet brush",
        grant_date=date(2018, 3, 6),
        filing_date=date(2016, 8, 23),
        kind="B2",
        num_claims=2,
        cpc_codes=["A47K11/10"],
        children=children,
        terminal_disclaimer=td,
    )


def test_related_continuation_child_flagged() -> None:
    related: list[RelatedRecord] = related_records(make(["US-9999916"]), [], [])
    assert [(r.relation, r.patent_key) for r in related] == [("continuation", "US-9999916")]
    assert related[0].status_to_verify
    assert related_flags(related) == ["related_active_continuation"]


def test_related_reissue_detected() -> None:
    related: list[RelatedRecord] = related_records(make(["US-RE47917"]), [], [])
    assert related[0].relation == "reissue"


def test_citations_assignee_and_disclaimer() -> None:
    related: list[RelatedRecord] = related_records(
        make([], td=True), ["US-10500001"], ["US-10600002"]
    )
    relations: set[str] = {r.relation for r in related}
    assert relations == {"forward_citation", "same_assignee", "terminal_disclaimer"}
    assert related_flags(related) == []
