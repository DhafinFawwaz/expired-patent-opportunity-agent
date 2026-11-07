from datetime import date, timedelta
from typing import TYPE_CHECKING

from typing_extensions import TypedDict

from patentic.adapters.base import ClaimRecord, EvidenceRecord, PatentRecord
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import StatusEvent
from patentic.domain.screening import is_core_hit
from patentic.domain.status_rules import add_years
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import PipelineState
from patentic.report.illustration import ILLUSTRATION_KEY

if TYPE_CHECKING:
    from patentic.adapters.bigquery import Continuity
    from patentic.adapters.og_notices import OgIndex


class DiscoverUpdate(TypedDict, total=False):
    stage: str
    records: dict[str, PatentRecord]
    outages: list[str]


class IndexUpdate(TypedDict, total=False):
    stage: str
    coverage: ScanCoverage
    events: dict[str, list[StatusEvent]]
    evidence: dict[str, EvidenceRecord]
    outages: list[str]


class ClaimsUpdate(TypedDict, total=False):
    stage: str
    claims: dict[str, list[ClaimRecord]]
    records: dict[str, PatentRecord]
    outages: list[str]


def grant_window_for(lapse_from: date, lapse_to: date) -> tuple[date, date]:
    return add_years(lapse_from, -12), add_years(lapse_to, -4)


class BqDiscover:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> DiscoverUpdate:
        deps: Deps = self._deps
        if deps.fixtures:
            records: dict[str, PatentRecord] = {
                f.record.patent.key: f.record for f in deps.fixtures
            }
            emit("discovery", "fixtures", count=len(records))
            return {"stage": "discovery", "records": records}
        weeks: int = state["request"].lapse_window_weeks
        grant_from, grant_to = grant_window_for(deps.today - timedelta(weeks=weeks), deps.today)
        emit("discovery", "bigquery_start", grant_from=str(grant_from), grant_to=str(grant_to))
        try:
            found: list[PatentRecord] = deps.bq.discover(
                [*deps.cpc.core, *deps.cpc.supporting], grant_from, grant_to
            )
        except Exception as exc:  # noqa: BLE001  # any source failure becomes an outage record
            emit("discovery", "outage", source="bigquery", error=str(exc))
            return {"stage": "discovery", "records": {}, "outages": ["bigquery"]}
        kept: dict[str, PatentRecord] = {
            r.patent.key: r for r in found if is_core_hit(r.cpc_codes, deps.cpc)
        }
        emit("discovery", "bigquery_done", found=len(found), core=len(kept))
        return {"stage": "discovery", "records": kept}


class OgIndexNode:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> IndexUpdate:
        deps: Deps = self._deps
        keys: set[str] = set(state.get("records", {}))
        if deps.fixtures:
            events: dict[str, list[StatusEvent]] = {
                f.record.patent.key: f.events for f in deps.fixtures
            }
            evidence: dict[str, EvidenceRecord] = {
                e.evidence_id: e for f in deps.fixtures for e in f.evidence
            }
            return {
                "stage": "status_index",
                "coverage": deps.fixtures[0].coverage,
                "events": events,
                "evidence": evidence,
            }
        weeks: int = state["request"].lapse_window_weeks
        emit("status_index", "gazette_start", weeks=weeks, keys=len(keys))
        index: OgIndex = deps.og.fetch_window(weeks, deps.today, keep=keys)
        if index.coverage.weeks_fetched == 0:
            emit("status_index", "outage", source="og_notice")
            return {"stage": "status_index", "coverage": index.coverage, "outages": ["og_notice"]}
        expired: set[str] = set(index.expirations()) & keys
        shown: set[str] = expired | (
            {ILLUSTRATION_KEY} & (set(index.reinstatements()) | set(index.expirations()))
        )
        found_events: dict[str, list[StatusEvent]] = {k: index.events_for(k) for k in shown}
        found_evidence: dict[str, EvidenceRecord] = {
            e.evidence_id: e for k in shown for e in index.evidence_for(k)
        }
        emit(
            "status_index",
            "gazette_done",
            weeks_fetched=index.coverage.weeks_fetched,
            missing=len(index.coverage.missing_weeks),
            expired_candidates=len(expired),
        )
        return {
            "stage": "status_index",
            "coverage": index.coverage,
            "events": found_events,
            "evidence": found_evidence,
        }


class BqClaims:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> ClaimsUpdate:
        deps: Deps = self._deps
        keys: list[str] = sorted(state.get("events", {}))
        if deps.fixtures:
            claims: dict[str, list[ClaimRecord]] = {
                f.record.patent.key: f.claims for f in deps.fixtures
            }
            return {"stage": "claims", "claims": claims}
        if not keys:
            return {"stage": "claims", "claims": {}}
        emit("claims", "bigquery_start", patents=len(keys))
        try:
            found: dict[str, list[ClaimRecord]] = deps.bq.claims(keys)
            links: dict[str, Continuity] = deps.bq.continuity(keys)
        except Exception as exc:  # noqa: BLE001  # any source failure becomes an outage record
            emit("claims", "outage", source="bigquery", error=str(exc))
            return {"stage": "claims", "claims": {}, "outages": ["bigquery"]}
        records: dict[str, PatentRecord] = {}
        for key in keys:
            info: Continuity | None = links.get(key)
            record: PatentRecord | None = state.get("records", {}).get(key)
            if record is not None and info is not None:
                records[key] = record.model_copy(
                    update={
                        "parents": list(info.parents),
                        "children": list(info.children),
                        "relation_types": {**info.parents, **info.children},
                        "terminal_disclaimer": info.terminal_disclaimer,
                    }
                )
        emit("claims", "bigquery_done", patents=len(found))
        return {"stage": "claims", "claims": found, "records": records}
