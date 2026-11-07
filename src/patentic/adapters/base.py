import hashlib
from collections.abc import Sequence
from datetime import date, datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from patentic.domain.confidence import Credibility, SourceGrade
from patentic.domain.events import EventType, Source
from patentic.domain.identifiers import PatentId

MAX_SNIPPET: Final[int] = 2000
EntityStatus = Literal["large", "small", "micro", "unknown"]


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    source: Source
    url: str
    retrieved_at: datetime
    from_cache: bool = False
    http_status: int | None
    raw_snippet: str
    content_sha256: str
    parser_version: str
    patent_key: str | None = None
    event_type: EventType | None = None
    event_date: date | None = None
    is_synthetic: bool = False
    source_grade: SourceGrade
    credibility: Credibility

    @field_validator("raw_snippet")
    @classmethod
    def _truncate(cls, value: str) -> str:
        return value[:MAX_SNIPPET]


def make_evidence_id(source: Source, url: str, retrieved_at: datetime, snippet: str) -> str:
    payload: str = f"{source}|{url}|{retrieved_at.isoformat()}|{snippet}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class PatentRecord(BaseModel):
    patent: PatentId
    title: str
    grant_date: date
    filing_date: date
    kind: str
    num_claims: int
    cpc_codes: list[str]
    entity_status: EntityStatus = "unknown"
    assignees: list[str] = []
    family_key: str | None = None
    parents: list[str] = []
    children: list[str] = []
    relation_types: dict[str, str] = {}
    terminal_disclaimer: bool | None = None


class ClaimRecord(BaseModel):
    patent_key: str
    sequence: int
    text: str
    dependent_on: int | None = None


def independent_claims(claims: Sequence[ClaimRecord]) -> list[ClaimRecord]:
    return [c for c in claims if c.dependent_on is None]
