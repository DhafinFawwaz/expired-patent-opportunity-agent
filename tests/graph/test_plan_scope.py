from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from patentic.adapters.base import ClaimRecord, PatentRecord
from patentic.domain.search_scope import SearchScope, resolve_scope
from patentic.graph.deps import Deps
from patentic.graph.nodes.normalise import screen_record
from patentic.graph.state import Candidate
from patentic.llm.schemas import PlanDraft, PlanRevision
from tests.graph.helpers import PLAN_ARGS, REQUEST, compile_graph, make_deps, run_until_interrupt
from tests.graph.test_discovery_verify import FakeBq, FakeOg, record
from tests.llm.fakes import scripted, tool_reply

CONFIG: RunnableConfig = {"configurable": {"thread_id": "t1"}}
WIDE: dict[str, object] = {**PLAN_ARGS, "cpc_codes": ["A47L13/", "A47L4/00 (Holders)"]}


class RecordingBq(FakeBq):
    def __init__(
        self, tmp_path: Path, records: list[PatentRecord], universe: list[PatentRecord] | None
    ) -> None:
        super().__init__(tmp_path, records)
        self.universe: list[PatentRecord] | None = universe
        self.prefixes: list[str] = []

    def discover(
        self, cpc_prefixes: Sequence[str], grant_from: date, grant_to: date
    ) -> list[PatentRecord]:
        self.prefixes = list(cpc_prefixes)
        return self.records

    def probe(
        self, subclasses: Sequence[str], grant_from: date, grant_to: date
    ) -> list[PatentRecord]:
        if self.universe is None:
            msg = "no cached probe"
            raise RuntimeError(msg)
        return self.universe


def run(deps: Deps) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    graph = compile_graph(deps)
    payloads: list[dict[str, Any]] = run_until_interrupt(graph, {"request": REQUEST})
    run_until_interrupt(graph, Command(resume={"action": "approve"}))
    values: dict[str, Any] = graph.get_state(CONFIG).values
    return payloads, values


def test_approved_plan_codes_reach_discovery(tmp_path: Path) -> None:
    bq: RecordingBq = RecordingBq(
        tmp_path, [record("8826466", ["A47L4/02"]), record("7000001", ["A47J1/00"])], None
    )
    tools = scripted(tool_reply(PlanDraft, WIDE))
    payloads, values = run(make_deps(tmp_path, tools=tools, og=FakeOg(), bq=bq))
    assert payloads[0]["scope"]["added"] == ["A47L4/"]
    assert bq.prefixes[-1] == "A47L4/"
    assert set(values["records"]) == {"US-8826466"}


def test_default_plan_sends_the_default_prefixes(tmp_path: Path) -> None:
    bq: RecordingBq = RecordingBq(tmp_path, [], None)
    deps: Deps = make_deps(tmp_path, og=FakeOg(), bq=bq)
    run(deps)
    assert bq.prefixes == [*deps.cpc.core, *deps.cpc.supporting]


def test_refine_round_adds_a_probed_group(tmp_path: Path) -> None:
    universe: list[PatentRecord] = [
        record("8000001", ["A47L13/20", "A47L4/02"]),
        record("8000002", ["A47L4/02"]),
    ]
    bq: RecordingBq = RecordingBq(tmp_path, [], universe)
    revision: dict[str, object] = {**WIDE, "done": True, "change_note": "added holders"}
    tools = scripted(tool_reply(PlanDraft, PLAN_ARGS), tool_reply(PlanRevision, revision))
    deps: Deps = make_deps(tmp_path, tools=tools, og=FakeOg(), bq=bq)
    deps = Deps(**{**deps.__dict__, "refine_rounds": 2})
    payloads, values = run(deps)
    assert [p["round"] for p in payloads[0]["probes"]] == [1]
    assert payloads[0]["probes"][0]["neighbours"][0]["group"] == "A47L4/"
    assert values["scope"].added == ["A47L4/"]
    assert bq.prefixes[-1] == "A47L4/"
    assert [c.call for c in values["calls"]][:2] == ["plan", "refine:1"]


def test_unavailable_probe_leaves_the_plan_unrefined(tmp_path: Path) -> None:
    bq: RecordingBq = RecordingBq(tmp_path, [], None)
    deps: Deps = make_deps(tmp_path, og=FakeOg(), bq=bq)
    deps = Deps(**{**deps.__dict__, "refine_rounds": 2})
    payloads, values = run(deps)
    assert payloads[0]["probes"] == []
    assert values["plan"].cpc_codes == ["A47L13/"]


def test_plan_power_terms_flag_instead_of_drop(tmp_path: Path) -> None:
    deps: Deps = make_deps(tmp_path)
    scope: SearchScope = resolve_scope(["A47L13/"], ["machine"], deps.cpc, deps.power)
    claim: ClaimRecord = ClaimRecord(
        patent_key="US-8826466", sequence=1, text="A mop with a machine washable pad."
    )
    candidate: Candidate = screen_record(record("8826466", ["A47L13/20"]), [claim], deps, scope)
    assert candidate.screening.passed
    assert candidate.flags == ["plan_term:machine"]
