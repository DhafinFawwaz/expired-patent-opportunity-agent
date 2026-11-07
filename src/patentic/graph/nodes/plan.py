from typing import Final, Literal

from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from patentic.graph.deps import Deps
from patentic.graph.state import ApprovalDecision, PipelineState
from patentic.llm.schemas import CallMeta, PlanDraft

MAX_REVISIONS: Final[int] = 3


class IntakeUpdate(TypedDict, total=False):
    stage: str
    revisions: int
    plan_feedback: list[str]


class PlanUpdate(TypedDict, total=False):
    stage: str
    plan: PlanDraft
    calls: list[CallMeta]


def intake(state: PipelineState) -> IntakeUpdate:
    return {"stage": "intake", "revisions": state.get("revisions", 0), "plan_feedback": []}


class PlanNode:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> PlanUpdate:
        plan, meta = self._deps.llm.plan(state["request"], state.get("plan_feedback", []))
        return {"stage": "plan", "plan": plan, "calls": [meta]}


def approve(state: PipelineState) -> Command[Literal["plan", "discover", "approve", "__end__"]]:
    revisions: int = state.get("revisions", 0)
    exhausted: bool = revisions >= MAX_REVISIONS
    payload: dict[str, object] = {
        "kind": "plan_approval",
        "plan": state["plan"].model_dump(),
        "revisions": revisions,
        "revisions_exhausted": exhausted,
        "options": ["approve", "abort"] if exhausted else ["approve", "revise", "abort"],
    }
    decision: ApprovalDecision = interrupt(payload, response_schema=ApprovalDecision)
    if decision.action == "approve":
        return Command(goto="discover", update={"approval": decision, "stage": "discover"})
    if decision.action == "abort":
        return Command(goto="__end__", update={"approval": decision, "stage": "aborted"})
    if exhausted:
        return Command(goto="approve", update={"approval": decision})
    feedback: list[str] = [*state.get("plan_feedback", []), decision.feedback or ""]
    return Command(
        goto="plan",
        update={"approval": decision, "plan_feedback": feedback, "revisions": revisions + 1},
    )
