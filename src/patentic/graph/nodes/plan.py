from datetime import date, timedelta
from typing import Final, Literal

from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from patentic.adapters.base import PatentRecord
from patentic.domain.request import ResearchRequest
from patentic.domain.search_scope import (
    ProbeReport,
    SearchScope,
    allowed_subclasses,
    probe_scope,
    resolve_scope,
)
from patentic.graph.deps import Deps
from patentic.graph.nodes.discover import grant_window_for
from patentic.graph.progress import emit
from patentic.graph.state import ApprovalDecision, PipelineState
from patentic.llm.schemas import CallMeta, PlanDraft, RefineContext

MAX_REVISIONS: Final[int] = 3


class IntakeUpdate(TypedDict, total=False):
    stage: str
    revisions: int
    plan_feedback: list[str]


class PlanUpdate(TypedDict, total=False):
    stage: str
    plan: PlanDraft
    scope: SearchScope
    probes: list[ProbeReport]
    calls: list[CallMeta]


def intake(state: PipelineState) -> IntakeUpdate:
    return {"stage": "intake", "revisions": state.get("revisions", 0), "plan_feedback": []}


class PlanNode:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> PlanUpdate:
        deps: Deps = self._deps
        request: ResearchRequest = state["request"]
        feedback: list[str] = state.get("plan_feedback", [])
        plan, meta = deps.llm.plan(request, feedback)
        calls: list[CallMeta] = [meta]
        scope: SearchScope = self._scope(plan)
        probes: list[ProbeReport] = []
        universe: list[PatentRecord] | None = (
            self._universe(request) if deps.refine_rounds else None
        )
        for round_no in range(1, deps.refine_rounds + 1):
            if universe is None:
                break
            probe: ProbeReport = probe_scope(universe, scope, deps.cpc, round_no)
            probes.append(probe)
            emit("plan", "probe", round=round_no, hits=probe.scoped_hits, added=len(scope.added))
            grant_from, grant_to = self._window(request)
            revision, meta = deps.llm.refine_plan(
                RefineContext(
                    request=request,
                    plan=plan,
                    feedback=feedback,
                    probe=describe_probe(probe),
                    subclasses=allowed_subclasses(deps.cpc),
                    grant_from=grant_from,
                    grant_to=grant_to,
                    round=round_no,
                )
            )
            calls.append(meta)
            if revision is None:
                break
            plan = PlanDraft.model_validate(revision.model_dump(exclude={"done", "change_note"}))
            scope = self._scope(plan)
            emit("plan", "refined", round=round_no, note=revision.change_note[:120])
            if revision.done:
                break
        return {"stage": "plan", "plan": plan, "scope": scope, "probes": probes, "calls": calls}

    def _scope(self, plan: PlanDraft) -> SearchScope:
        return resolve_scope(plan.cpc_codes, plan.exclusion_terms, self._deps.cpc, self._deps.power)

    def _window(self, request: ResearchRequest) -> tuple[date, date]:
        today: date = self._deps.today
        return grant_window_for(today - timedelta(weeks=request.lapse_window_weeks), today)

    def _universe(self, request: ResearchRequest) -> list[PatentRecord] | None:
        grant_from, grant_to = self._window(request)
        try:
            return self._deps.bq.probe(allowed_subclasses(self._deps.cpc), grant_from, grant_to)
        except Exception as exc:  # noqa: BLE001  # without the probe the plan simply goes unrefined
            emit("plan", "probe_unavailable", error=str(exc)[:200])
            return None


def describe_probe(probe: ProbeReport) -> str:
    summary: str = (
        f"Baseline CPC set finds {probe.baseline_hits} patents; "
        f"the current plan finds {probe.scoped_hits}."
    )
    lines: list[str] = [summary]
    for added in probe.added:
        titles: str = "; ".join(added.sample_titles) or "none"
        lines.append(
            f"Added {added.code}: {added.matches} patents, {added.passing} not powered by CPC. "
            f"Sample titles: {titles}"
        )
    if probe.neighbours:
        lines.append("Groups that co-occur with current hits but are not searched:")
        lines.extend(
            f"- {n.group}: on {n.co_occurring} current hits, {n.new_patents} new patents, "
            f"e.g. {n.sample_title or 'no new title'}"
            for n in probe.neighbours
        )
    lines.extend(f"Ignored {r.code}: {r.reason}" for r in probe.rejected)
    return "\n".join(lines)


def approve(state: PipelineState) -> Command[Literal["plan", "discover", "approve", "__end__"]]:
    revisions: int = state.get("revisions", 0)
    exhausted: bool = revisions >= MAX_REVISIONS
    payload: dict[str, object] = {
        "kind": "plan_approval",
        "plan": state["plan"].model_dump(),
        "scope": state["scope"].model_dump() if "scope" in state else None,
        "probes": [p.model_dump() for p in state.get("probes", [])],
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
