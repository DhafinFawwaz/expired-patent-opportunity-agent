from collections.abc import Sequence
from datetime import date
from typing import Final, NamedTuple, Self

from pydantic import BaseModel, Field, model_validator

from patentic.config.loaders import read_yaml
from patentic.domain.confidence import Confidence
from patentic.domain.related import RelatedRecord

_CONFIDENCE_SCORE: Final[dict[Confidence, int]] = {
    "very_high": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "very_low": 1,
}
_CONFIDENCE_RANK: Final[dict[Confidence, int]] = _CONFIDENCE_SCORE
_LINEAGE: Final[frozenset[str]] = frozenset({"continuation", "division", "cip"})
_REINSTATEMENT_RISK_DAYS: Final[int] = 365


class ScoringWeights(BaseModel):
    commercial_relevance: float = 0.35
    engineering_effort: float = 0.20
    evidence_quality: float = 0.25
    unresolved_risk: float = 0.20
    analysis_pool: int = Field(default=8, ge=1)

    @model_validator(mode="after")
    def _sum_to_one(self) -> Self:
        total: float = (
            self.commercial_relevance
            + self.engineering_effort
            + self.evidence_quality
            + self.unresolved_risk
        )
        if abs(total - 1.0) > 1e-6:  # noqa: PLR2004
            msg = f"weights must sum to 1, got {total}"
            raise ValueError(msg)
        return self


class Scores(BaseModel):
    commercial_relevance: int = Field(ge=1, le=5)
    engineering_effort: int = Field(ge=1, le=5)
    evidence_quality: int = Field(ge=1, le=5)
    unresolved_risk: int = Field(ge=1, le=5)
    total: float


class PoolEntry(NamedTuple):
    key: str
    confidence: Confidence
    lapse_date: date
    entity_status: str
    independent_claims: int


def load_weights() -> ScoringWeights:
    return ScoringWeights.model_validate(read_yaml("scoring.yaml"))


def evidence_quality_score(confidence: Confidence, n_sources: int) -> int:
    if n_sources == 0:
        return 1
    return _CONFIDENCE_SCORE[confidence]


def unresolved_risk_score(
    related: Sequence[RelatedRecord],
    lapsed_days_ago: int | None,
    terminal_disclaimer: bool | None,  # noqa: FBT001
) -> int:
    score: int = 1
    score += min(2, sum(1 for r in related if r.relation in _LINEAGE))
    score += any(r.relation == "forward_citation" for r in related)
    score += any(r.relation in {"same_assignee", "reissue"} for r in related)
    if lapsed_days_ago is not None and lapsed_days_ago < _REINSTATEMENT_RISK_DAYS:
        score += 1
    if terminal_disclaimer:
        score += 1
    return max(1, min(5, score))


def total_score(
    commercial: int, effort: int, evidence: int, risk: int, weights: ScoringWeights
) -> float:
    return round(
        weights.commercial_relevance * commercial
        + weights.engineering_effort * (6 - effort)
        + weights.evidence_quality * evidence
        + weights.unresolved_risk * (6 - risk),
        4,
    )


def rank_pool(candidates: Sequence[PoolEntry], pool: int) -> list[str]:
    ordered: list[PoolEntry] = sorted(
        candidates,
        key=lambda c: (
            -_CONFIDENCE_RANK[c.confidence],
            -c.lapse_date.toordinal(),
            c.entity_status not in {"small", "micro"},
            c.independent_claims,
        ),
    )
    return [c.key for c in ordered[:pool]]
