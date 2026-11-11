from typing import TYPE_CHECKING

from langgraph.types import Send
from typing_extensions import TypedDict

from patentic.adapters.base import EvidenceRecord
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import StatusEvent
from patentic.domain.related import RelatedRecord, related_flags, related_records
from patentic.domain.status_rules import StatusAssessment, assess_status
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import Candidate, PipelineState

if TYPE_CHECKING:
    from patentic.adapters.fixtures import FixtureCase


class VerifyInput(TypedDict):
    candidate: Candidate
    events: list[StatusEvent]
    coverage: ScanCoverage


class VerifyUpdate(TypedDict, total=False):
    candidates: dict[str, Candidate]
    evidence: dict[str, EvidenceRecord]


def verify_dispatch(state: PipelineState) -> list[Send] | str:
    coverage: ScanCoverage | None = state.get("coverage")
    sends: list[Send] = [
        Send(
            "verify_candidate",
            {
                "candidate": candidate,
                "events": state.get("events", {}).get(key, []),
                "coverage": coverage or ScanCoverage(weeks_fetched=0),
            },
        )
        for key, candidate in state.get("candidates", {}).items()
        if candidate.screening.passed
    ]
    return sends or "rank"


class VerifyCandidate:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: VerifyInput) -> VerifyUpdate:
        candidate: Candidate = state["candidate"]
        record = candidate.record
        events: list[StatusEvent] = list(state["events"])
        evidence: dict[str, EvidenceRecord] = {}
        for event, item in self._deps.ops.events_for(record.patent):
            events.append(event)
            evidence[item.evidence_id] = item
        assessment: StatusAssessment = assess_status(
            record.patent,
            record.grant_date,
            record.filing_date,
            events,
            state["coverage"],
            self._deps.today,
        )
        fixture: FixtureCase | None = next(
            (f for f in self._deps.fixtures if f.record.patent.key == candidate.key), None
        )
        children: list[str] = [r.patent.key for r in fixture.related] if fixture else []
        related: list[RelatedRecord] = related_records(
            record.model_copy(update={"children": [*record.children, *children]}), [], []
        )
        emit(
            "status",
            "assessed",
            key=candidate.key,
            label=assessment.label,
            confidence=assessment.confidence,
        )
        updated: Candidate = candidate.model_copy(
            update={
                "assessment": assessment,
                "related": related,
                "flags": [*candidate.flags, *related_flags(related)],
            }
        )
        return {"candidates": {candidate.key: updated}, "evidence": evidence}
