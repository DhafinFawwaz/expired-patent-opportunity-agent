from datetime import date
from pathlib import Path
from typing import Any

import pydantic
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from patentic.adapters.base import PatentRecord
from patentic.adapters.fixtures import FixtureCase, load_fixtures
from patentic.domain.confidence import Confidence
from patentic.domain.identifiers import parse_patent_number
from patentic.domain.scoring import Scores
from patentic.domain.status_rules import StatusAssessment
from patentic.graph.deps import Deps
from patentic.graph.nodes.score import assign_recommendations
from patentic.graph.state import Candidate, Recommendation, ScreeningResult
from patentic.llm.schemas import OpportunityRationale, TechnicalSummary
from tests.graph.helpers import REQUEST, compile_graph, make_deps, plan_replies, run_until_interrupt
from tests.llm.fakes import scripted, tool_reply

ROOT: Path = Path(__file__).parents[2]
CONFIG: RunnableConfig = {"configurable": {"thread_id": "t1"}}
FIXTURES: list[FixtureCase] = load_fixtures(ROOT / "fixtures" / "synthetic")


def tech(powered: str, quotes: list[str] | None = None) -> AIMessage:
    return tool_reply(
        TechnicalSummary,
        {
            "summary": "A manual cleaning tool.",
            "mechanism": "Hand operated.",
            "key_claim_elements": ["frame"],
            "implementation_unknowns": ["materials"],
            "powered": powered,
            "evidence_ids": [],
            "quotes": quotes or [],
        },
    )


def opp(commercial: int, effort: int) -> AIMessage:
    return tool_reply(
        OpportunityRationale,
        {
            "commercial_relevance": commercial,
            "engineering_effort": effort,
            "applications": ["home cleaning"],
            "challenges": ["tooling"],
            "rationale": "Simple to make.",
            "evidence_ids": [],
        },
    )


def graph_to_review(
    tmp_path: Path, *replies: AIMessage
) -> tuple[CompiledStateGraph[Any, Any, Any, Any], list[dict[str, Any]]]:
    deps: Deps = make_deps(tmp_path, tools=scripted(*plan_replies(1), *replies))
    deps = Deps(**{**deps.__dict__, "fixtures": tuple(FIXTURES)})
    graph = compile_graph(deps)
    run_until_interrupt(graph, {"request": REQUEST})
    payloads: list[dict[str, Any]] = run_until_interrupt(
        graph, Command(resume={"action": "approve"})
    )
    return graph, payloads


def test_analyse_marks_powered_as_excluded(tmp_path: Path) -> None:
    graph, _ = graph_to_review(tmp_path, tech("non_powered"), tech("powered"), opp(4, 2))
    candidates: dict[str, Candidate] = graph.get_state(CONFIG).values["candidates"]
    assert candidates["US-9999906"].screening.tier3 == "powered"
    assert candidates["US-9999906"].recommendation == "Exclude"
    assert candidates["US-9999901"].recommendation == "Shortlist"


def test_analyse_quote_verification_failure_uses_fallback(tmp_path: Path) -> None:
    bad: AIMessage = tech("non_powered", ["a motor spins the pad"])
    graph, _ = graph_to_review(tmp_path, bad, bad, tech("non_powered"), opp(3, 3), opp(3, 3))
    candidates: dict[str, Candidate] = graph.get_state(CONFIG).values["candidates"]
    assert candidates["US-9999901"].screening.tier3 == "unclear"
    assert "powered_unclear" in candidates["US-9999901"].flags


def test_score_shortlists_top_two_passed_candidates(tmp_path: Path) -> None:
    graph, _ = graph_to_review(
        tmp_path, tech("non_powered"), tech("non_powered"), opp(5, 2), opp(3, 4)
    )
    candidates: dict[str, Candidate] = graph.get_state(CONFIG).values["candidates"]
    first: Candidate = candidates["US-9999901"]
    second: Candidate = candidates["US-9999906"]
    assert first.scores is not None
    assert second.scores is not None
    assert first.scores.total > second.scores.total
    assert (first.recommendation, second.recommendation) == ("Shortlist", "Shortlist")


def scored(key: str, total: float, confidence: Confidence) -> Candidate:
    return Candidate(
        key=key,
        record=PatentRecord(
            patent=parse_patent_number(key),
            title="t",
            grant_date=date(2014, 1, 1),
            filing_date=date(2012, 1, 1),
            kind="B2",
            num_claims=1,
            cpc_codes=["A47L13/20"],
        ),
        assessment=StatusAssessment(
            label="expired_nonpayment", as_of=date(2026, 11, 7), confidence=confidence
        ),
        screening=ScreeningResult(core_hit=True, passed=True),
        scores=Scores(
            commercial_relevance=3,
            engineering_effort=3,
            evidence_quality=3,
            unresolved_risk=3,
            total=total,
        ),
    )


def test_low_confidence_never_shortlisted() -> None:
    result: dict[str, Recommendation] = assign_recommendations(
        [
            scored("US-1000001", 4.5, "low"),
            scored("US-1000002", 3.0, "high"),
            scored("US-1000003", 2.0, "medium"),
        ],
        max_recommended=2,
    )
    assert result == {"US-1000001": "Hold", "US-1000002": "Shortlist", "US-1000003": "Shortlist"}


def test_review_interrupt_payload_lists_candidates_and_not_analysed_count(tmp_path: Path) -> None:
    _, payloads = graph_to_review(
        tmp_path, tech("non_powered"), tech("non_powered"), opp(4, 2), opp(3, 3)
    )
    payload: dict[str, Any] = payloads[0]
    assert payload["kind"] == "candidate_review"
    assert {row["key"] for row in payload["candidates"]} >= {"US-9999901", "US-9999906"}
    assert payload["not_analysed"] == 0
    assert payload["max_recommended"] == 2


def test_review_shortlist_limit(tmp_path: Path) -> None:
    graph, _ = graph_to_review(
        tmp_path, tech("non_powered"), tech("non_powered"), opp(4, 2), opp(3, 3)
    )
    with pytest.raises(pydantic.ValidationError):
        run_until_interrupt(
            graph,
            Command(
                resume={"action": "edit", "shortlist": ["US-9999901", "US-9999906", "US-9999902"]}
            ),
        )
    run_until_interrupt(graph, Command(resume={"action": "accept"}))
    assert graph.get_state(CONFIG).values["review"].action == "accept"


def test_review_edit_applies_drops(tmp_path: Path) -> None:
    graph, _ = graph_to_review(
        tmp_path, tech("non_powered"), tech("non_powered"), opp(4, 2), opp(3, 3)
    )
    decision: dict[str, object] = {
        "action": "edit",
        "drop": ["US-9999906"],
        "flag": {"US-9999901": "check the pad clip"},
        "shortlist": ["US-9999901"],
    }
    run_until_interrupt(graph, Command(resume=decision))
    candidates: dict[str, Candidate] = graph.get_state(CONFIG).values["candidates"]
    assert candidates["US-9999906"].recommendation == "Exclude"
    assert candidates["US-9999906"].reviewer_note == "dropped at review"
    assert candidates["US-9999901"].reviewer_note == "check the pad clip"
    assert candidates["US-9999901"].recommendation == "Shortlist"
