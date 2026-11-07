from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from patentic.graph.deps import Deps
from patentic.graph.nodes.plan import PlanNode, approve, intake
from patentic.graph.state import InputState, PipelineState


class EmptyUpdate(TypedDict, total=False):
    stage: str


def _discover_placeholder(state: PipelineState) -> EmptyUpdate:  # noqa: ARG001
    return {}


def build_graph(
    deps: Deps, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[PipelineState, None, InputState, PipelineState]:
    graph: StateGraph[PipelineState, None, InputState, PipelineState] = StateGraph(
        PipelineState, input_schema=InputState
    )
    graph.add_node("intake", intake)
    graph.add_node("plan", PlanNode(deps))
    graph.add_node("approve", approve, destinations=("plan", "discover", "approve", END))
    graph.add_node("discover", _discover_placeholder)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "plan")
    graph.add_edge("plan", "approve")
    graph.add_edge("discover", END)
    return graph.compile(checkpointer=checkpointer)
