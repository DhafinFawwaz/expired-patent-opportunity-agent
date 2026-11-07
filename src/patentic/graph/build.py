from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from patentic.graph.deps import Deps
from patentic.graph.nodes.analyse import Analyse
from patentic.graph.nodes.bundle import Bundle
from patentic.graph.nodes.discover import BqClaims, BqDiscover, OgIndexNode
from patentic.graph.nodes.normalise import Normalise
from patentic.graph.nodes.plan import PlanNode, approve, intake
from patentic.graph.nodes.rank import Rank
from patentic.graph.nodes.review import review
from patentic.graph.nodes.score import Score
from patentic.graph.nodes.verify import VerifyCandidate, verify_dispatch
from patentic.graph.state import InputState, PipelineState


def build_graph(
    deps: Deps, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[PipelineState, None, InputState, PipelineState]:
    graph: StateGraph[PipelineState, None, InputState, PipelineState] = StateGraph(
        PipelineState, input_schema=InputState
    )
    graph.add_node("intake", intake)
    graph.add_node("plan", PlanNode(deps))
    graph.add_node("approve", approve, destinations=("plan", "discover", "approve", END))
    graph.add_node("discover", BqDiscover(deps))
    graph.add_node("status_index", OgIndexNode(deps))
    graph.add_node("claims", BqClaims(deps))
    graph.add_node("normalise", Normalise(deps))
    graph.add_node("verify_candidate", VerifyCandidate(deps))
    graph.add_node("rank", Rank(deps))
    graph.add_node("analyse", Analyse(deps))
    graph.add_node("score", Score(deps))
    graph.add_node("review", review, destinations=("bundle", END))
    graph.add_node("bundle", Bundle(deps))
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "plan")
    graph.add_edge("plan", "approve")
    graph.add_edge("discover", "status_index")
    graph.add_edge("status_index", "claims")
    graph.add_edge("claims", "normalise")
    graph.add_conditional_edges("normalise", verify_dispatch, ["verify_candidate", "rank"])
    graph.add_edge("verify_candidate", "rank")
    graph.add_edge("rank", "analyse")
    graph.add_edge("analyse", "score")
    graph.add_edge("score", "review")
    graph.add_edge("bundle", END)
    return graph.compile(checkpointer=checkpointer)
