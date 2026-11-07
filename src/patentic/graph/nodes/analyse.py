from typing_extensions import TypedDict

from patentic.adapters.base import ClaimRecord, independent_claims
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import Candidate, PipelineState
from patentic.llm.schemas import CallMeta, TechnicalContext


class AnalyseUpdate(TypedDict, total=False):
    stage: str
    candidates: dict[str, Candidate]
    calls: list[CallMeta]


def technical_context(candidate: Candidate, claims: list[ClaimRecord]) -> TechnicalContext:
    independent: list[ClaimRecord] = independent_claims(claims)
    first: str = independent[0].text if independent else candidate.record.title
    evidence: list[str] = candidate.assessment.evidence_ids if candidate.assessment else []
    return TechnicalContext(
        patent_key=candidate.key,
        title=candidate.record.title,
        abstract_or_first_claim=first,
        text="\n".join(c.text for c in claims) or candidate.record.title,
        evidence_ids=evidence,
    )


class Analyse:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> AnalyseUpdate:
        candidates: dict[str, Candidate] = state.get("candidates", {})
        claims: dict[str, list[ClaimRecord]] = state.get("claims", {})
        updated: dict[str, Candidate] = {}
        calls: list[CallMeta] = []
        for key in state.get("pool", []):
            candidate: Candidate = candidates[key]
            summary, meta = self._deps.llm.technical(
                technical_context(candidate, claims.get(key, []))
            )
            calls.append(meta)
            flags: list[str] = list(candidate.flags)
            if summary.powered == "unclear" and "powered_unclear" not in flags:
                flags.append("powered_unclear")
            screening = candidate.screening.model_copy(
                update={"tier3": summary.powered, "passed": summary.powered != "powered"}
            )
            emit(
                "technical",
                "summarised",
                key=key,
                powered=summary.powered,
                method=meta.method,
                error=meta.last_error,
            )
            updated[key] = candidate.model_copy(
                update={
                    "technical": summary,
                    "screening": screening,
                    "flags": flags,
                    "recommendation": "Exclude" if summary.powered == "powered" else None,
                }
            )
        return {"stage": "technical", "candidates": updated, "calls": calls}
