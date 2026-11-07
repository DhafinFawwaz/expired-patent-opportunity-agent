import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final, Protocol
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from patentic.adapters.base import EvidenceRecord, make_evidence_id, sha256_text
from patentic.adapters.http import utc_now
from patentic.domain.events import EventType, StatusEvent, map_inpadoc_code
from patentic.domain.identifiers import PatentId

PARSER_VERSION: Final[str] = "ops-legal-1"
NS: Final[dict[str, str]] = {"ops": "http://ops.epo.org"}
CACHE_TTL: Final[timedelta] = timedelta(hours=24)
_EFFECTIVE_TEXT: Final[re.Pattern[str]] = re.compile(
    r"EFFECTIVE DATE:?\s*(\d{8}|\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
_OPS_URL: Final[str] = "https://ops.epo.org/3.2/rest-services/legal/publication/epodoc/{}"


class LegalFetchError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status: int = status


class LegalFetcher(Protocol):
    def fetch(self, epodoc: str) -> str: ...


class EpoOpsFetcher:
    def __init__(self, key: str, secret: str) -> None:
        import epo_ops  # noqa: PLC0415  # only needed when credentials exist

        self._epo_ops = epo_ops
        self._client = epo_ops.Client(key=key, secret=secret)

    def fetch(self, epodoc: str) -> str:
        try:
            response = self._client.legal("publication", self._epo_ops.models.Epodoc(epodoc))
        except Exception as exc:
            status: int = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            raise LegalFetchError(status, str(exc)) from exc
        text: str = str(response.text)
        return text


def _date(text: str) -> date:
    digits: str = text.strip().replace("-", "")
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))


def _field(node: Element, name: str) -> str | None:
    found: Element | None = node.find(f"ops:{name}", NS)
    return found.text.strip() if found is not None and found.text else None


def parse_legal_xml(
    xml: str, patent: PatentId, url: str, retrieved_at: datetime
) -> list[tuple[StatusEvent, EvidenceRecord]]:
    root: Element = ElementTree.fromstring(xml)
    pairs: list[tuple[StatusEvent, EvidenceRecord]] = []
    for node in root.iter(f"{{{NS['ops']}}}legal"):
        code: str = (node.get("code") or "").strip()
        desc: str = node.get("desc") or ""
        free_text: str = " ".join(t.strip() for t in node.itertext() if t.strip())
        event_type: EventType | None = map_inpadoc_code(code, f"{desc} {free_text}")
        gazette: str | None = _field(node, "L007EP")
        if event_type is None or gazette is None:
            continue
        effective_raw: str | None = _field(node, "L525EP")
        if effective_raw is None and (found := _EFFECTIVE_TEXT.search(free_text)):
            effective_raw = found[1]
        snippet: str = f"{code} {gazette} {desc} {free_text}".strip()
        evidence_id: str = make_evidence_id("ops", url, retrieved_at, snippet)
        event: StatusEvent = StatusEvent(
            event_type=event_type,
            event_date=_date(gazette),
            effective_date=_date(effective_raw) if effective_raw else None,
            source="ops",
            source_code=code,
            evidence_id=evidence_id,
        )
        evidence: EvidenceRecord = EvidenceRecord(
            evidence_id=evidence_id,
            source="ops",
            url=url,
            retrieved_at=retrieved_at,
            http_status=200,
            raw_snippet=snippet,
            content_sha256=sha256_text(snippet),
            parser_version=PARSER_VERSION,
            patent_key=patent.key,
            event_type=event_type,
            event_date=event.event_date,
            source_grade="B",
            credibility=2,
        )
        pairs.append((event, evidence))
    return pairs


class OpsLegalSource:
    def __init__(
        self,
        key: str | None,
        secret: str | None,
        cache_dir: Path,
        fetcher: LegalFetcher | None = None,
    ) -> None:
        self.enabled: bool = bool(key and secret)
        self._cache_dir: Path = cache_dir / "ops"
        self._fetcher: LegalFetcher | None = fetcher
        if self.enabled and fetcher is None and key and secret:
            self._fetcher = EpoOpsFetcher(key, secret)

    def events_for(self, patent: PatentId) -> list[tuple[StatusEvent, EvidenceRecord]]:
        if not self.enabled or self._fetcher is None:
            return []
        epodoc: str = f"US{patent.prefix}{patent.number}"
        url: str = _OPS_URL.format(epodoc)
        path: Path = self._cache_dir / f"{epodoc}.xml"
        now: datetime = utc_now()
        if (
            path.exists()
            and now - datetime.fromtimestamp(path.stat().st_mtime, now.tzinfo) < CACHE_TTL
        ):
            return parse_legal_xml(path.read_text(), patent, url, now)
        try:
            xml: str = self._fetcher.fetch(epodoc)
        except LegalFetchError as exc:
            return [_outage(patent, url, now, str(exc))]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml)
        return parse_legal_xml(xml, patent, url, now)


def _outage(
    patent: PatentId, url: str, at: datetime, message: str
) -> tuple[StatusEvent, EvidenceRecord]:
    snippet: str = f"EPO OPS unavailable: {message}"
    evidence_id: str = make_evidence_id("ops", url, at, snippet)
    event: StatusEvent = StatusEvent(
        event_type="outage",
        event_date=at.date(),
        source="ops",
        source_code="OUTAGE",
        evidence_id=evidence_id,
    )
    evidence: EvidenceRecord = EvidenceRecord(
        evidence_id=evidence_id,
        source="ops",
        url=url,
        retrieved_at=at,
        http_status=None,
        raw_snippet=snippet,
        content_sha256=sha256_text(snippet),
        parser_version=PARSER_VERSION,
        patent_key=patent.key,
        event_type="outage",
        event_date=at.date(),
        source_grade="B",
        credibility=6,
    )
    return event, evidence
