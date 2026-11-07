from collections.abc import Sequence
from datetime import date
from typing import Final, Literal

from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import EventType, Source, StatusEvent

Confidence = Literal["very_low", "low", "medium", "high", "very_high"]
SourceGrade = Literal["A", "B", "C", "D", "E", "F"]
Credibility = Literal[1, 2, 3, 4, 5, 6]

_STATUS_GRADES: Final[dict[Source, SourceGrade]] = {
    "og_notice": "A",
    "ops": "B",
    "odp": "A",
    "bigquery": "F",
    "fixture": "F",
}
_BIBLIOGRAPHIC_GRADES: Final[dict[Source, SourceGrade]] = {
    "og_notice": "A",
    "ops": "B",
    "odp": "A",
    "bigquery": "A",
    "fixture": "F",
}
_DECISIVE: Final[dict[str, frozenset[EventType]]] = {
    "expired_nonpayment": frozenset({"lapse"}),
    "reinstated": frozenset({"reinstated", "petition_granted"}),
}


def grade_for_source(source: Source, field_kind: Literal["status", "bibliographic"]) -> SourceGrade:
    table: dict[Source, SourceGrade] = (
        _STATUS_GRADES if field_kind == "status" else _BIBLIOGRAPHIC_GRADES
    )
    return table[source]


def credibility_for(n_independent_sources: int, *, official: bool) -> Credibility:
    if n_independent_sources >= 2:  # noqa: PLR2004
        return 1
    if n_independent_sources == 1:
        return 2 if official else 3
    return 6


def compute_confidence(
    label: str,
    events: Sequence[StatusEvent],
    coverage: ScanCoverage,
    effective_date: date | None,
) -> Confidence:
    if label in {"expired_end_of_term", "unknown"}:
        return "very_low"
    if label == "conflicting":
        return "low"
    if label == "not_subject_to_maintenance_fees":
        return "very_high"
    decisive: frozenset[EventType] = _DECISIVE.get(label, frozenset())
    agreeing: set[Source] = {e.source for e in events if e.event_type in decisive}
    if "og_notice" not in agreeing:
        return "medium"
    scan_complete: bool = label == "reinstated" or (
        effective_date is not None and coverage.covers_after(effective_date)
    )
    if not scan_complete:
        return "medium"
    return "very_high" if len(agreeing) >= 2 else "high"  # noqa: PLR2004
