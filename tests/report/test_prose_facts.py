from patentic.graph.nodes.bundle import prose_facts
from patentic.report.bundle import CandidateReport, FlowCounts, ReportBundle

FLOW: FlowCounts = FlowCounts(
    found=2404,
    expired_in_window=299,
    passed_screening=209,
    status_verified=210,
    analysed=8,
    not_analysed=201,
    recommended=2,
)


def test_each_section_gets_a_brief(bundle: ReportBundle) -> None:
    for section in ("executive_summary", "methodology", "commercial", "next_steps"):
        facts: dict[str, object] = prose_facts(section, bundle.candidates, FLOW, 104, [])
        assert isinstance(facts["brief"], str)
        assert facts["brief"]


def test_methodology_sees_counts_but_no_candidates(bundle: ReportBundle) -> None:
    facts: dict[str, object] = prose_facts("methodology", bundle.candidates, FLOW, 104, [])
    assert "flow" in facts
    assert "candidates" not in facts


def test_commercial_and_next_steps_skip_the_counts(bundle: ReportBundle) -> None:
    reports: list[CandidateReport] = bundle.candidates
    commercial: dict[str, object] = prose_facts("commercial", reports, FLOW, 104, [])
    steps: dict[str, object] = prose_facts("next_steps", reports, FLOW, 104, [])
    assert "flow" not in commercial
    assert "flow" not in steps
    shortlisted: list[str] = [r.display for r in reports if r.recommendation == "Shortlist"]
    assert [c["patent"] for c in steps["candidates"]] == shortlisted  # type: ignore[attr-defined]


def test_executive_summary_gets_only_the_two_headline_counts(bundle: ReportBundle) -> None:
    facts: dict[str, object] = prose_facts("executive_summary", bundle.candidates, FLOW, 104, [])
    assert facts["counts"] == {
        "patents_searched": 2404,
        "listed_expired_for_nonpayment_in_window": 299,
    }
    assert "flow" not in facts
