import os
from datetime import UTC, date, datetime
from pathlib import Path

from patentic.adapters.base import EvidenceRecord
from patentic.adapters.ops_legal import LegalFetchError, OpsLegalSource, parse_legal_xml
from patentic.domain.events import StatusEvent
from patentic.domain.identifiers import PatentId, parse_patent_number

XML: str = (
    Path(__file__).parents[1] / "data" / "ops" / "legal-US8646606-synthetic.xml"
).read_text()
PATENT: PatentId = parse_patent_number("8,646,606")
AT: datetime = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)


def test_parse_legal_xml_maps_laps_fp_and_payments() -> None:
    pairs: list[tuple[StatusEvent, EvidenceRecord]] = parse_legal_xml(
        XML, PATENT, "https://ops/x", AT
    )
    codes: list[tuple[str, str]] = [(e.source_code, e.event_type) for e, _ in pairs]
    assert codes == [
        ("FPAY", "fee_paid"),
        ("FEPP", "reminder"),
        ("LAPS", "lapse"),
        ("STCH", "lapse"),
        ("FP", "lapse"),
    ]
    fp: StatusEvent = next(e for e, _ in pairs if e.source_code == "FP")
    assert fp.event_date == date(2026, 4, 7)
    assert fp.effective_date == date(2026, 2, 11)
    evidence: EvidenceRecord = pairs[0][1]
    assert (evidence.source, evidence.source_grade, evidence.patent_key) == (
        "ops",
        "B",
        "US-8646606",
    )


class FakeFetcher:
    def __init__(self, xml: str | None = None, error: int | None = None) -> None:
        self.xml: str | None = xml
        self.error: int | None = error
        self.calls: int = 0

    def fetch(self, epodoc: str) -> str:
        self.calls += 1
        if self.error is not None:
            raise LegalFetchError(self.error, "quota exceeded")
        return self.xml or ""


def test_disabled_source_returns_nothing(tmp_path: Path) -> None:
    source: OpsLegalSource = OpsLegalSource(None, None, tmp_path)
    assert not source.enabled
    assert source.events_for(PATENT) == []


def test_enabled_source_uses_fetcher_and_caches(tmp_path: Path) -> None:
    fetcher: FakeFetcher = FakeFetcher(XML)
    source: OpsLegalSource = OpsLegalSource("k", "s", tmp_path, fetcher=fetcher)
    assert len(source.events_for(PATENT)) == 5
    assert len(source.events_for(PATENT)) == 5
    assert fetcher.calls == 1


def test_quota_403_not_retried(tmp_path: Path) -> None:
    fetcher: FakeFetcher = FakeFetcher(error=403)
    source: OpsLegalSource = OpsLegalSource("k", "s", tmp_path, fetcher=fetcher)
    pairs: list[tuple[StatusEvent, EvidenceRecord]] = source.events_for(PATENT)
    assert fetcher.calls == 1
    assert [e.event_type for e, _ in pairs] == ["outage"]
    assert "403" in pairs[0][1].raw_snippet


def test_offline_source_reads_stale_cache_and_never_fetches(tmp_path: Path) -> None:
    OpsLegalSource("k", "s", tmp_path, fetcher=FakeFetcher(XML)).events_for(PATENT)
    cached: Path = next((tmp_path / "ops").glob("*.xml"))
    os.utime(cached, (0, 0))
    fetcher: FakeFetcher = FakeFetcher(XML)
    offline: OpsLegalSource = OpsLegalSource("k", "s", tmp_path, fetcher=fetcher, offline=True)
    assert len(offline.events_for(PATENT)) == 5
    assert fetcher.calls == 0


def test_offline_cache_miss_returns_nothing(tmp_path: Path) -> None:
    fetcher: FakeFetcher = FakeFetcher(XML)
    offline: OpsLegalSource = OpsLegalSource("k", "s", tmp_path, fetcher=fetcher, offline=True)
    assert offline.events_for(PATENT) == []
    assert fetcher.calls == 0
