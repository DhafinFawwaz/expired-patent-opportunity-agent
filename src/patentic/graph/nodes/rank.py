from typing_extensions import TypedDict

from patentic.adapters.base import independent_claims
from patentic.domain.scoring import PoolEntry, rank_pool
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import Candidate, PipelineState


class RankUpdate(TypedDict, total=False):
    stage: str
    pool: list[str]
    candidates: dict[str, Candidate]


class Rank:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> RankUpdate:
        candidates: dict[str, Candidate] = state.get("candidates", {})
        claims = state.get("claims", {})
        entries: list[PoolEntry] = [
            PoolEntry(
                c.key,
                c.assessment.confidence,
                c.assessment.effective_date or self._deps.today,
                c.record.entity_status,
                len(independent_claims(claims.get(c.key, []))) or 1,
            )
            for c in candidates.values()
            if c.screening.passed and c.assessment and c.assessment.label == "expired_nonpayment"
        ]
        pool: list[str] = rank_pool(entries, self._deps.weights.analysis_pool)
        eligible: set[str] = {e.key for e in entries}
        updated: dict[str, Candidate] = {}
        for key, candidate in candidates.items():
            if key in pool:
                continue
            verdict: str = "NotAnalysed" if key in eligible else "Exclude"
            updated[key] = candidate.model_copy(update={"recommendation": verdict})
        emit("rank", "pool", analysed=len(pool), not_analysed=len(eligible) - len(pool))
        return {"stage": "rank", "pool": pool, "candidates": updated}
