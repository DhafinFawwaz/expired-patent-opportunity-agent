from typing import Literal

from langgraph.types import Command, interrupt

from patentic.graph.state import Candidate, PipelineState, ReviewDecision


def review_payload(state: PipelineState) -> dict[str, object]:
    candidates: dict[str, Candidate] = state.get("candidates", {})
    rows: list[dict[str, object]] = [
        {
            "key": c.key,
            "title": c.record.title,
            "status": c.assessment.label if c.assessment else "unknown",
            "confidence": c.assessment.confidence if c.assessment else "very_low",
            "total": c.scores.total if c.scores else None,
            "recommendation": c.recommendation,
            "flags": c.flags,
            "synthetic": c.is_synthetic,
        }
        for c in sorted(candidates.values(), key=lambda c: -(c.scores.total if c.scores else -1.0))
        if c.scores is not None
    ]
    return {
        "kind": "candidate_review",
        "candidates": rows,
        "not_analysed": sum(1 for c in candidates.values() if c.recommendation == "NotAnalysed"),
        "max_recommended": state["request"].max_recommended,
        "options": ["accept", "edit", "abort"],
    }


def review(state: PipelineState) -> Command[Literal["bundle", "__end__"]]:
    decision: ReviewDecision = interrupt(review_payload(state), response_schema=ReviewDecision)
    if decision.action == "abort":
        return Command(goto="__end__", update={"review": decision, "stage": "aborted"})
    candidates: dict[str, Candidate] = state.get("candidates", {})
    updated: dict[str, Candidate] = {}
    if decision.action == "edit":
        limit: int = state["request"].max_recommended
        # Only analysed candidates can be shortlisted; the report shows nothing else.
        chosen: list[str] = [
            k for k in decision.shortlist if k in candidates and candidates[k].scores is not None
        ][:limit]
        for key, candidate in candidates.items():
            changes: dict[str, object] = {}
            if key in decision.drop:
                changes = {"recommendation": "Exclude", "reviewer_note": "dropped at review"}
            elif decision.shortlist:
                if key in chosen:
                    changes["recommendation"] = "Shortlist"
                elif candidate.recommendation == "Shortlist":
                    changes["recommendation"] = "Hold"
            if key in decision.flag:
                changes["reviewer_note"] = decision.flag[key]
            if changes:
                updated[key] = candidate.model_copy(update=changes)
    return Command(
        goto="bundle", update={"review": decision, "candidates": updated, "stage": "review"}
    )
