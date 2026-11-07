import calendar
from collections.abc import Sequence
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel

from patentic.domain.confidence import Confidence, compute_confidence
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import EventType, Stage, StatusEvent
from patentic.domain.identifiers import PatentId

__all__ = [
    "ScanCoverage",
    "StatusAssessment",
    "StatusLabel",
    "anniversaries",
    "assess_status",
    "due_dates",
]

StatusLabel = Literal[
    "expired_nonpayment",
    "reinstated",
    "in_grace_period",
    "petition_pending",
    "expired_end_of_term",
    "conflicting",
    "in_force",
    "not_subject_to_maintenance_fees",
    "unknown",
]

STAGES: Final[tuple[Stage, Stage, Stage]] = (4, 8, 12)
TERM_YEARS: Final[int] = 20
_REVIVALS: Final[frozenset[EventType]] = frozenset({"reinstated", "petition_granted"})
_OFFICIAL: Final[str] = "og_notice"


class StatusAssessment(BaseModel):
    label: StatusLabel
    as_of: date
    effective_date: date | None = None
    stage: Stage | None = None
    evidence_ids: list[str] = []
    timeline: list[StatusEvent] = []
    notes: list[str] = []
    confidence: Confidence = "very_low"


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def add_months(d: date, months: int) -> date:
    total: int = d.month - 1 + months
    year: int = d.year + total // 12
    month: int = total % 12 + 1
    last_day: int = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def anniversaries(grant: date) -> tuple[date, date, date]:
    return (add_years(grant, 4), add_years(grant, 8), add_years(grant, 12))


def due_dates(grant: date) -> tuple[date, date, date]:
    return (
        add_months(add_years(grant, 3), 6),
        add_months(add_years(grant, 7), 6),
        add_months(add_years(grant, 11), 6),
    )


def assess_status(
    patent: PatentId,
    grant_date: date,
    filing_date: date,
    events: Sequence[StatusEvent],
    coverage: ScanCoverage,
    today: date,
) -> StatusAssessment:
    timeline: list[StatusEvent] = _dedupe(events)
    base: StatusAssessment = StatusAssessment(
        label="unknown",
        as_of=today,
        timeline=timeline,
        evidence_ids=[e.evidence_id for e in timeline],
    )
    if not patent.maintenance_eligible:
        return _with_confidence(
            base.model_copy(
                update={
                    "label": "not_subject_to_maintenance_fees",
                    "notes": ["Design and plant patents pay no maintenance fees."],
                }
            ),
            coverage,
        )
    lapses: list[StatusEvent] = [e for e in timeline if e.event_type == "lapse"]
    result: StatusAssessment = (
        _assess_after_lapse(base, timeline, lapses, grant_date, coverage)
        if lapses
        else _assess_without_lapse(base, timeline, grant_date, filing_date, today)
    )
    return _with_confidence(result, coverage)


def _assess_after_lapse(
    base: StatusAssessment,
    timeline: list[StatusEvent],
    lapses: list[StatusEvent],
    grant: date,
    coverage: ScanCoverage,
) -> StatusAssessment:
    # Order by legal effect: a lapse counts from its expiry, not from the notice that prints it.
    def legal(e: StatusEvent) -> tuple[date, bool, bool]:
        on: date = _lapse_date(e, grant) if e.event_type == "lapse" else e.event_date
        return (on, e.event_type in _REVIVALS, e.source == _OFFICIAL)

    decisive: list[StatusEvent] = sorted(
        [e for e in timeline if e.event_type == "lapse" or e.event_type in _REVIVALS], key=legal
    )
    last: StatusEvent = decisive[-1]
    expiry: date = max(_lapse_date(e, grant) for e in lapses if legal(e) <= legal(last))
    stage: Stage | None = _stage_for(expiry, grant)
    notes: list[str] = []

    if last.event_type in _REVIVALS:
        if last.source != _OFFICIAL and any(e.source == _OFFICIAL for e in lapses):
            notes.append(
                f"{last.source} reports a revival on {last.event_date} but the official notice "
                "still shows the lapse; no later official notice settles it."
            )
            return base.model_copy(
                update={
                    "label": "conflicting",
                    "effective_date": expiry,
                    "stage": stage,
                    "notes": notes,
                }
            )
        notes.append(
            f"Reinstated on {last.event_date}. Intervening rights may protect anyone who started "
            f"using the invention between {expiry} and {last.event_date}."
        )
        notes.extend(_lagging_notes(last, lapses))
        return base.model_copy(
            update={"label": "reinstated", "effective_date": expiry, "stage": stage, "notes": notes}
        )

    later: list[StatusEvent] = [e for e in timeline if e.event_date > expiry]
    if any(e.event_type == "petition_filed" for e in later) and not any(
        e.event_type == "petition_denied" for e in later
    ):
        notes.append(
            "A petition to accept the late fee was filed after the lapse and is undecided."
        )
        return base.model_copy(
            update={
                "label": "petition_pending",
                "effective_date": expiry,
                "stage": stage,
                "notes": notes,
            }
        )
    if any(e.event_type == "fee_paid" for e in later):
        notes.append(
            "A fee payment is recorded after the lapse with no petition or reinstatement; "
            "it may be a short or misapplied payment."
        )
        return base.model_copy(
            update={
                "label": "conflicting",
                "effective_date": expiry,
                "stage": stage,
                "notes": notes,
            }
        )
    if not coverage.covers_after(expiry):
        notes.append(
            f"Reinstatement lists were not checked for every week after {expiry}; "
            "a later reinstatement could be missing."
        )
    return base.model_copy(
        update={
            "label": "expired_nonpayment",
            "effective_date": expiry,
            "stage": stage,
            "notes": notes,
        }
    )


def _assess_without_lapse(
    base: StatusAssessment,
    timeline: list[StatusEvent],
    grant: date,
    filing: date,
    today: date,
) -> StatusAssessment:
    term_end: date = add_years(filing, TERM_YEARS)
    if term_end <= today:
        return base.model_copy(
            update={
                "label": "expired_end_of_term",
                "effective_date": term_end,
                "notes": [
                    (
                        f"Twenty years from filing ended on {term_end}. PTA unknown, so the real "
                        "end may be later; a terminal disclaimer could make it earlier."
                    )
                ],
            }
        )
    has_fee_data: bool = any(e.event_type in {"fee_paid", "reminder"} for e in timeline)
    for due, anniversary, stage in zip(due_dates(grant), anniversaries(grant), STAGES, strict=True):
        if due < today <= anniversary and has_fee_data and not _paid(timeline, anniversary, stage):
            return base.model_copy(
                update={
                    "label": "in_grace_period",
                    "effective_date": anniversary,
                    "stage": stage,
                    "notes": [
                        f"Fee unpaid; the patent expires at the end of {anniversary} unless paid."
                    ],
                }
            )
    for anniversary, stage in zip(anniversaries(grant), STAGES, strict=True):
        if anniversary < today and not _paid(timeline, anniversary, stage):
            return base.model_copy(
                update={
                    "stage": stage,
                    "notes": [
                        (
                            f"No payment evidence for the {stage}-year fee and no lapse notice "
                            "yet; the notice may still be unpublished."
                        )
                    ],
                }
            )
    return base.model_copy(update={"label": "in_force"})


def _with_confidence(result: StatusAssessment, coverage: ScanCoverage) -> StatusAssessment:
    confidence: Confidence = compute_confidence(
        result.label, result.timeline, coverage, result.effective_date
    )
    return result.model_copy(update={"confidence": confidence})


def _dedupe(events: Sequence[StatusEvent]) -> list[StatusEvent]:
    seen: set[tuple[str, date, str, str]] = set()
    unique: list[StatusEvent] = []
    for event in sorted(events, key=lambda e: e.event_date):
        key: tuple[str, date, str, str] = (
            event.event_type,
            event.event_date,
            event.source_code,
            event.source,
        )
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return unique


def _lapse_date(event: StatusEvent, grant: date) -> date:
    if event.effective_date is not None:
        return event.effective_date
    past: list[date] = [a for a in anniversaries(grant) if a <= event.event_date]
    return past[-1] if past else event.event_date


def _stage_for(expiry: date, grant: date) -> Stage | None:
    for anniversary, stage in zip(anniversaries(grant), STAGES, strict=True):
        if abs((expiry - anniversary).days) <= 1:
            return stage
    return None


def _paid(timeline: list[StatusEvent], anniversary: date, stage: Stage) -> bool:
    window_start: date = add_years(anniversary, -1)
    return any(
        e.event_type == "fee_paid"
        and (e.stage == stage or (e.stage is None and window_start < e.event_date <= anniversary))
        for e in timeline
    )


def _lagging_notes(winner: StatusEvent, lapses: list[StatusEvent]) -> list[str]:
    sources: list[str] = sorted({e.source for e in lapses if e.source != winner.source})
    return [
        f"{winner.source} dated later than {source}; {source} has not caught up yet."
        for source in sources
    ]
