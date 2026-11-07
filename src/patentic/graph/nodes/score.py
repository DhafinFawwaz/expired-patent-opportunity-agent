from collections.abc import Sequence
from typing import Final

from typing_extensions import TypedDict

from patentic.domain.related import RelatedRecord, related_records
from patentic.domain.scoring import (
    Scores,
    evidence_quality_score,
    total_score,
    unresolved_risk_score,
)
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import Candidate, PipelineState, Recommendation
from patentic.llm.schemas import CallMeta, OpportunityContext, OpportunityRationale

SHORTLIST_CONFIDENCE: Final[frozenset[str]] = frozenset({"medium", "high", "very_high"})


class ScoreUpdate(TypedDict, total=False):
    stage: str
    candidates: dict[str, Candidate]
    calls: list[CallMeta]
    outages: list[str]


def assign_recommendations(
    scored: Sequence[Candidate], max_recommended: int
) -> dict[str, Recommendation]:
    ranked: list[Candidate] = sorted(
        scored, key=lambda c: (-(c.scores.total if c.scores else 0.0), c.key)
    )
    result: dict[str, Recommendation] = {}
    shortlisted: int = 0
    for candidate in ranked:
        confident: bool = bool(
            candidate.assessment and candidate.assessment.confidence in SHORTLIST_CONFIDENCE
        )
        if confident and shortlisted < max_recommended:
            result[candidate.key] = "Shortlist"
            shortlisted += 1
        else:
            result[candidate.key] = "Hold"
    return result


class Score:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> ScoreUpdate:
        deps: Deps = self._deps
        candidates: dict[str, Candidate] = state.get("candidates", {})
        pool: list[str] = [k for k in state.get("pool", []) if candidates[k].screening.passed]
        outages: list[str] = []
        citations: dict[str, list[str]] = {}
        if pool and not deps.fixtures:
            try:
                everyone: list[str] = sorted(state.get("records", {}))
                citations = deps.bq.forward_citations(pool, prefetch=everyone)
            except Exception:  # noqa: BLE001  # citations are optional evidence
                outages.append("bigquery")
        scored: list[Candidate] = []
        calls: list[CallMeta] = []
        for key in pool:
            candidate: Candidate = candidates[key]
            assessment = candidate.assessment
            related: list[RelatedRecord] = [
                *candidate.related,
                *related_records(
                    candidate.record.model_copy(update={"children": [], "parents": []}),
                    citations.get(key, []),
                    [],
                ),
            ]
            ctx: OpportunityContext = OpportunityContext(
                patent_key=key,
                title=candidate.record.title,
                summary=candidate.technical.summary
                if candidate.technical
                else candidate.record.title,
                status=assessment.label if assessment else "unknown",
                evidence_ids=assessment.evidence_ids if assessment else [],
                category=state["request"].technology_category,
                intended_product=state["request"].intended_product,
            )
            rationale, meta = deps.llm.opportunity(ctx)
            calls.append(meta)
            lapsed: int | None = (
                (deps.today - assessment.effective_date).days
                if assessment and assessment.effective_date
                else None
            )
            sources: int = len({e.source for e in assessment.timeline}) if assessment else 0
            evidence: int = (
                evidence_quality_score(assessment.confidence, sources) if assessment else 1
            )
            risk: int = unresolved_risk_score(related, lapsed, candidate.record.terminal_disclaimer)
            scores: Scores = Scores(
                commercial_relevance=rationale.commercial_relevance,
                engineering_effort=rationale.engineering_effort,
                evidence_quality=evidence,
                unresolved_risk=risk,
                total=total_score(
                    rationale.commercial_relevance,
                    rationale.engineering_effort,
                    evidence,
                    risk,
                    deps.weights,
                ),
            )
            scored.append(_scored(candidate, rationale, scores, related))
        verdicts: dict[str, Recommendation] = assign_recommendations(
            scored, state["request"].max_recommended
        )
        updated: dict[str, Candidate] = {
            c.key: c.model_copy(update={"recommendation": verdicts[c.key]}) for c in scored
        }
        emit(
            "screening",
            "scored",
            scored=len(scored),
            shortlisted=sum(v == "Shortlist" for v in verdicts.values()),
        )
        return {"stage": "screening", "candidates": updated, "calls": calls, "outages": outages}


def _scored(
    candidate: Candidate,
    rationale: OpportunityRationale,
    scores: Scores,
    related: list[RelatedRecord],
) -> Candidate:
    return candidate.model_copy(
        update={"opportunity": rationale, "scores": scores, "related": related}
    )
