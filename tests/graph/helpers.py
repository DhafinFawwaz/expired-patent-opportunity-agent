from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from patentic.adapters.bigquery import BigQueryGateway, BytesLedger
from patentic.adapters.http import HttpSource, outage_transport
from patentic.adapters.og_notices import OgIndexer
from patentic.adapters.ops_legal import OpsLegalSource
from patentic.config.settings import Settings
from patentic.domain.request import ResearchRequest
from patentic.domain.scoring import load_weights
from patentic.domain.screening import load_cpc_sets, load_power_terms
from patentic.graph.build import build_graph
from patentic.graph.deps import Deps
from patentic.llm.calls import LlmCaller
from patentic.llm.schemas import PlanDraft
from tests.llm.fakes import ScriptedChatModel, scripted, tool_reply

TODAY: date = date(2026, 11, 7)
REQUEST: ResearchRequest = ResearchRequest(
    technology_category="non-powered household cleaning tools",
    intended_product="manual mops and brushes",
)
PLAN_ARGS: dict[str, object] = {
    "search_terms": ["mop"],
    "cpc_codes": ["A47L13/"],
    "exclusion_terms": ["motor"],
    "sources": ["Official Gazette"],
    "screening_criteria": ["no power"],
    "output_structure": ["report"],
}


def plan_replies(n: int) -> list[AIMessage]:
    return [tool_reply(PlanDraft, PLAN_ARGS) for _ in range(n)]


def make_deps(
    tmp_path: Path,
    tools: ScriptedChatModel | None = None,
    og: OgIndexer | None = None,
    bq: BigQueryGateway | None = None,
) -> Deps:
    http: HttpSource = HttpSource(
        "og", tmp_path, None, 1000.0, "t", transport=outage_transport(404), sleep=lambda _s: None
    )
    llm: LlmCaller = LlmCaller(
        tools or scripted(*plan_replies(6)), scripted(), None, UsageMetadataCallbackHandler()
    )
    return Deps(
        settings=Settings(_env_file=None),
        og=og or OgIndexer(http),
        bq=bq
        or BigQueryGateway(
            None, tmp_path / "bq", BytesLedger(tmp_path / "ledger.json"), offline=True
        ),
        ops=OpsLegalSource(None, None, tmp_path),
        llm=llm,
        weights=load_weights(),
        cpc=load_cpc_sets(),
        power=load_power_terms(),
        today=TODAY,
    )


def compile_graph(deps: Deps) -> CompiledStateGraph[Any, Any, Any, Any]:
    return build_graph(deps, InMemorySaver())


def run_until_interrupt(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    payload: dict[str, object] | Command[Any],
    thread: str = "t1",
) -> list[dict[str, Any]]:
    interrupts: list[dict[str, Any]] = []
    chunks: Iterator[dict[str, Any] | Any] = graph.stream(
        payload, {"configurable": {"thread_id": thread}}, stream_mode="updates"
    )
    for chunk in chunks:
        if isinstance(chunk, dict) and "__interrupt__" in chunk:
            interrupts.extend(i.value for i in chunk["__interrupt__"])
    return interrupts
