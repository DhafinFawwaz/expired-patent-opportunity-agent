from datetime import date
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from patentic.adapters.base import EvidenceRecord
from patentic.domain.events import StatusEvent

ILLUSTRATION_KEY: Final[str] = "US-8646606"
OBSERVATION_FILE: Final[Path] = Path("fixtures") / "observations" / "US-8646606-google-patents.json"


class Observation(BaseModel):
    patent_key: str
    title: str
    grant_date: date
    filing_date: date
    note: str
    events: list[StatusEvent]
    evidence: list[EvidenceRecord]


def load_observation(path: Path = OBSERVATION_FILE) -> Observation | None:
    return Observation.model_validate_json(path.read_text()) if path.exists() else None
