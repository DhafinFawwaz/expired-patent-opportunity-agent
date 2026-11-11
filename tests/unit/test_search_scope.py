from datetime import date

import pytest

from patentic.adapters.base import PatentRecord
from patentic.domain.identifiers import parse_patent_number
from patentic.domain.screening import CpcSets, PowerTerms, load_cpc_sets, load_power_terms
from patentic.domain.search_scope import (
    ProbeReport,
    SearchScope,
    normalise_cpc,
    plan_terms,
    probe_scope,
    resolve_scope,
    scoped_sets,
)

SETS: CpcSets = load_cpc_sets()
TERMS: PowerTerms = load_power_terms()


def rec(number: str, cpc: list[str], title: str = "Tool") -> PatentRecord:
    return PatentRecord(
        patent=parse_patent_number(number),
        title=title,
        grant_date=date(2015, 1, 6),
        filing_date=date(2013, 1, 1),
        kind="B2",
        num_claims=3,
        cpc_codes=cpc,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A47L 13/00 (Cleaning implements)", "A47L13/"),
        ("A47L13/16", "A47L13/16"),
        ("a47l13", "A47L13/"),
        ("A47L", None),
        ("A46B (Brushes)", None),
        ("mops", None),
    ],
)
def test_normalise_cpc(raw: str, expected: str | None) -> None:
    assert normalise_cpc(raw) == expected


def test_recorded_style_plan_keeps_the_default_query() -> None:
    codes: list[str] = ["A47L (Domestic)", "A47L 13/00 (Cleaning implements)", "A47L 13/10"]
    scope: SearchScope = resolve_scope(codes, [], SETS, TERMS)
    assert scope.added == []
    assert scope.prefixes == [*SETS.core, *SETS.supporting]
    assert scope.already_covered == ["A47L13/", "A47L13/10"]
    assert [r.code for r in scope.rejected] == ["A47L (Domestic)"]


def test_new_group_is_added_and_counts_as_core() -> None:
    scope: SearchScope = resolve_scope(["A47L4/00"], [], SETS, TERMS)
    assert scope.added == ["A47L4/"]
    assert scope.prefixes[-1] == "A47L4/"
    assert scoped_sets(SETS, scope).core[-1] == "A47L4/"


def test_out_of_scope_and_powered_codes_are_rejected() -> None:
    scope: SearchScope = resolve_scope(["A47J43/28", "A47L9/28"], [], SETS, TERMS)
    assert scope.added == []
    reasons: list[str] = [r.reason for r in scope.rejected]
    assert reasons[0].startswith("outside the subclasses")
    assert reasons[1] == "a powered co-class the screen removes"


def test_plan_exclusion_terms_extend_the_claim_screen() -> None:
    scope: SearchScope = resolve_scope(
        [], ["Motor", "Robotic", "x", "cord; drop table"], SETS, TERMS
    )
    assert scope.exclusion_terms == ["robotic"]
    assert plan_terms(TERMS, scope).terms == ["robotic"]


def test_indexing_groups_are_not_suggested() -> None:
    records: list[PatentRecord] = [rec("8000001", ["A47L13/20", "A46B2200/3033"])]
    probe: ProbeReport = probe_scope(records, resolve_scope([], [], SETS, TERMS), SETS, 1)
    assert probe.neighbours == []


def test_probe_counts_added_codes_and_neighbours() -> None:
    records: list[PatentRecord] = [
        rec("8000001", ["A47L13/20", "A47L4/02"], "Mop with hook"),
        rec("8000002", ["A47L4/02"], "Wall-mounted holder"),
        rec("8000003", ["A47L4/02", "A47L9/28"], "Vacuum dock"),
    ]
    plain: ProbeReport = probe_scope(records, resolve_scope([], [], SETS, TERMS), SETS, 1)
    assert plain.baseline_hits == 1
    assert [(n.group, n.co_occurring, n.new_patents) for n in plain.neighbours] == [
        ("A47L4/", 1, 1)
    ]
    widened: ProbeReport = probe_scope(records, resolve_scope(["A47L4/"], [], SETS, TERMS), SETS, 2)
    assert widened.scoped_hits == 2
    assert widened.added[0].matches == 3
    assert widened.added[0].passing == 2
    assert widened.neighbours == []
