from datetime import date

import pytest

from patentic.domain.related import RelatedRecord
from patentic.domain.scoring import (
    PoolEntry,
    ScoringWeights,
    evidence_quality_score,
    load_weights,
    rank_pool,
    total_score,
    unresolved_risk_score,
)

WEIGHTS: ScoringWeights = load_weights()


def test_default_weights() -> None:
    assert (WEIGHTS.commercial_relevance, WEIGHTS.engineering_effort) == (0.35, 0.20)
    assert (WEIGHTS.evidence_quality, WEIGHTS.unresolved_risk) == (0.25, 0.20)
    assert WEIGHTS.analysis_pool == 8


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        ScoringWeights(commercial_relevance=0.5)


def test_scores_total_weights() -> None:
    assert total_score(3, 3, 3, 3, WEIGHTS) == pytest.approx(3.0)
    assert total_score(5, 3, 3, 3, WEIGHTS) > total_score(3, 3, 3, 3, WEIGHTS)
    assert total_score(3, 5, 3, 3, WEIGHTS) < total_score(3, 3, 3, 3, WEIGHTS)


def test_evidence_quality_follows_confidence() -> None:
    assert evidence_quality_score("very_high", 2) == 5
    assert evidence_quality_score("high", 1) == 4
    assert evidence_quality_score("low", 1) == 2
    assert evidence_quality_score("medium", 0) == 1


def test_unresolved_risk_counts_relations_and_recent_lapse() -> None:
    cont: RelatedRecord = RelatedRecord(
        relation="continuation", patent_key="US-2", source_field="children", evidence="child"
    )
    assert unresolved_risk_score([], lapsed_days_ago=900, terminal_disclaimer=None) == 1
    assert unresolved_risk_score([cont], lapsed_days_ago=200, terminal_disclaimer=None) == 3
    many: list[RelatedRecord] = [cont, cont, cont]
    assert unresolved_risk_score(many, lapsed_days_ago=100, terminal_disclaimer=True) == 5


def test_rank_pool_orders_and_truncates() -> None:
    entries: list[PoolEntry] = [
        PoolEntry("US-1", "medium", date(2026, 5, 1), "large", 3),
        PoolEntry("US-2", "high", date(2025, 5, 1), "large", 3),
        PoolEntry("US-3", "high", date(2026, 5, 1), "large", 9),
        PoolEntry("US-4", "high", date(2026, 5, 1), "small", 9),
        PoolEntry("US-5", "high", date(2026, 5, 1), "small", 2),
    ]
    assert rank_pool(entries, 3) == ["US-5", "US-4", "US-3"]
