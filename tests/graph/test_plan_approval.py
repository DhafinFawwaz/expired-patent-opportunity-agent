from pathlib import Path
from typing import Any

import pydantic
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from tests.graph.helpers import REQUEST, compile_graph, make_deps, run_until_interrupt

START: dict[str, object] = {"request": REQUEST}
CONFIG: RunnableConfig = {"configurable": {"thread_id": "t1"}}


def graph(tmp_path: Path) -> CompiledStateGraph[Any, Any, Any, Any]:
    return compile_graph(make_deps(tmp_path))


def test_stream_stops_at_approval_interrupt(tmp_path: Path) -> None:
    payloads: list[dict[str, Any]] = run_until_interrupt(graph(tmp_path), START)
    assert payloads[0]["kind"] == "plan_approval"
    assert payloads[0]["plan"]["cpc_codes"] == ["A47L13/"]
    assert payloads[0]["options"] == ["approve", "revise", "abort"]


def test_resume_approve_moves_to_discover(tmp_path: Path) -> None:
    g = graph(tmp_path)
    run_until_interrupt(g, START)
    run_until_interrupt(g, Command(resume={"action": "approve"}))
    snapshot = g.get_state(CONFIG)
    assert snapshot.values["approval"].action == "approve"
    assert "bigquery" in snapshot.values["outages"]


def test_resume_revise_replans_with_feedback(tmp_path: Path) -> None:
    g = graph(tmp_path)
    run_until_interrupt(g, START)
    payloads = run_until_interrupt(
        g, Command(resume={"action": "revise", "feedback": "fewer brushes"})
    )
    state: dict[str, Any] = g.get_state(CONFIG).values
    assert state["plan_feedback"] == ["fewer brushes"]
    assert state["revisions"] == 1
    assert payloads[0]["revisions"] == 1


def test_revision_cap_forces_decision(tmp_path: Path) -> None:
    g = graph(tmp_path)
    payloads = run_until_interrupt(g, START)
    for i in range(3):
        payloads = run_until_interrupt(g, Command(resume={"action": "revise", "feedback": f"r{i}"}))
    assert payloads[0]["revisions_exhausted"] is True
    assert payloads[0]["options"] == ["approve", "abort"]
    payloads = run_until_interrupt(g, Command(resume={"action": "revise", "feedback": "again"}))
    assert payloads[0]["kind"] == "plan_approval"
    assert g.get_state(CONFIG).values["revisions"] == 3


def test_invalid_resume_is_rejected_and_reaskable(tmp_path: Path) -> None:
    g = graph(tmp_path)
    run_until_interrupt(g, START)
    with pytest.raises(pydantic.ValidationError):
        run_until_interrupt(g, Command(resume={"action": "maybe"}))
    run_until_interrupt(g, Command(resume={"action": "approve"}))
    assert g.get_state(CONFIG).values["approval"].action == "approve"


def test_abort_ends_run(tmp_path: Path) -> None:
    g = graph(tmp_path)
    run_until_interrupt(g, START)
    run_until_interrupt(g, Command(resume={"action": "abort"}))
    snapshot = g.get_state(CONFIG)
    assert snapshot.values["approval"].action == "abort"
    assert snapshot.next == ()
