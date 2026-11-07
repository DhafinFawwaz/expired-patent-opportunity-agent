from collections.abc import Sequence

from typing_extensions import TypedDict

from patentic.adapters.base import ClaimRecord, PatentRecord, independent_claims
from patentic.domain.screening import is_core_hit, tier1_rejects, tier2_power_hits
from patentic.domain.status_rules import StatusAssessment
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import Candidate, PipelineState, ScreeningResult


class NormaliseUpdate(TypedDict, total=False):
    stage: str
    candidates: dict[str, Candidate]


def screen_record(record: PatentRecord, claims: Sequence[ClaimRecord], deps: Deps) -> Candidate:
    core: bool = is_core_hit(record.cpc_codes, deps.cpc)
    tier1: list[str] = tier1_rejects(record.cpc_codes, deps.cpc)
    tier2: list[str] = tier2_power_hits([c.text for c in independent_claims(claims)], deps.power)
    eligible: bool = record.patent.maintenance_eligible
    assessment: StatusAssessment | None = None
    if not eligible:
        assessment = StatusAssessment(
            label="not_subject_to_maintenance_fees",
            as_of=deps.today,
            confidence="very_high",
            notes=["Design and plant patents pay no maintenance fees."],
        )
    return Candidate(
        key=record.patent.key,
        record=record,
        assessment=assessment,
        screening=ScreeningResult(
            core_hit=core,
            tier1_rejects=tier1,
            tier2_hits=tier2,
            passed=eligible and core and not tier1 and not tier2,
        ),
        is_synthetic=bool(deps.fixtures),
    )


class Normalise:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> NormaliseUpdate:
        records: dict[str, PatentRecord] = state.get("records", {})
        claims: dict[str, list[ClaimRecord]] = state.get("claims", {})
        keys: list[str] = sorted(set(state.get("events", {})) & set(records))
        candidates: dict[str, Candidate] = {
            k: screen_record(records[k], claims.get(k, []), self._deps) for k in keys
        }
        passed: int = sum(1 for c in candidates.values() if c.screening.passed)
        emit("normalise", "screened", candidates=len(candidates), passed=passed)
        return {"stage": "normalise", "candidates": candidates}
