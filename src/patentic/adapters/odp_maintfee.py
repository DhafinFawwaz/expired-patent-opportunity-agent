import hashlib
from collections.abc import Sequence
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from patentic.domain.events import EventType, StatusEvent, map_usptofile_code, stage_from_code
from patentic.domain.identifiers import PatentId, parse_patent_number

Entity = Literal["Y", "M", "N"]


class MaintFeeLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    patent: PatentId
    application: str
    entity: Entity
    filing_date: date
    grant_date: date
    event_date: date
    code: str
    raw: str


def _yyyymmdd(text: str) -> date:
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def _entity(value: str) -> Entity:
    entities: dict[str, Entity] = {"Y": "Y", "M": "M", "N": "N"}
    return entities[value]


def parse_maintfee_line(line: str) -> MaintFeeLine:
    return MaintFeeLine(
        patent=parse_patent_number(line[0:13].strip()),
        application=line[14:22].strip(),
        entity=_entity(line[23]),
        filing_date=_yyyymmdd(line[25:33]),
        grant_date=_yyyymmdd(line[34:42]),
        event_date=_yyyymmdd(line[43:51]),
        code=line[52:57].strip(),
        raw=line.rstrip("\r\n"),
    )


def to_events(lines: Sequence[MaintFeeLine]) -> list[StatusEvent]:
    events: list[StatusEvent] = []
    seen: set[tuple[str, date, str]] = set()
    for line in sorted(lines, key=lambda item: item.event_date):
        event_type: EventType | None = map_usptofile_code(line.code)
        key: tuple[str, date, str] = (line.patent.key, line.event_date, line.code)
        if event_type is None or key in seen:
            continue
        seen.add(key)
        events.append(
            StatusEvent(
                event_type=event_type,
                event_date=line.event_date,
                stage=stage_from_code(line.code),
                source="odp",
                source_code=line.code,
                evidence_id=hashlib.sha256(f"odp|{line.raw}".encode()).hexdigest()[:12],
            )
        )
    return events


class OdpMaintFeeSource:
    """USPTO maintenance fee events. Needs an ODP key (ID.me verified); not exercised live here."""

    def __init__(self, api_key: str | None) -> None:
        self.enabled: bool = bool(api_key)
