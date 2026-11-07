from datetime import date
from pathlib import Path

from pydantic import BaseModel

from patentic.adapters.base import ClaimRecord, EvidenceRecord, PatentRecord
from patentic.domain.confidence import Confidence
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import StatusEvent
from patentic.domain.status_rules import StatusLabel


class FixtureExpectation(BaseModel):
    label: StatusLabel
    confidence: Confidence
    flags: list[str] = []


class FixtureCase(BaseModel):
    name: str
    description: str
    record: PatentRecord
    claims: list[ClaimRecord]
    events: list[StatusEvent]
    evidence: list[EvidenceRecord]
    coverage: ScanCoverage
    today: date
    related: list[PatentRecord] = []
    expected: FixtureExpectation


def load_fixtures(directory: Path) -> list[FixtureCase]:
    return [
        FixtureCase.model_validate_json(path.read_text())
        for path in sorted(directory.glob("*.json"))
    ]
