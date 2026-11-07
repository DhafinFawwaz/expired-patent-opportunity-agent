import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Final, Protocol

from pydantic import BaseModel

from patentic.adapters.base import ClaimRecord, PatentRecord
from patentic.adapters.bigquery_sql import CITATIONS_SQL, CLAIMS_SQL, CONTINUITY_SQL, DISCOVERY_SQL
from patentic.adapters.http import utc_now
from patentic.domain.identifiers import (
    IdentifierError,
    parse_application_number,
    parse_patent_number,
)

DEFAULT_MAX_BYTES: Final[int] = 50_000_000_000
_RELATIONS: Final[dict[str, str]] = {
    "continuation": "continuation",
    "continuation-in-part": "cip",
    "division": "division",
    "reissue": "reissue",
}
_CLAIM_REF: Final[re.Pattern[str]] = re.compile(r"\bclaims? (\d+)", re.IGNORECASE)

Row = dict[str, object]


class BigQueryBudgetError(RuntimeError):
    pass


class CacheMissError(RuntimeError):
    pass


class QueryRunner(Protocol):
    def dry_run(self, sql: str, params: Mapping[str, object]) -> int: ...

    def run(
        self, sql: str, params: Mapping[str, object], max_bytes: int
    ) -> tuple[list[Row], int]: ...


class Continuity(BaseModel):
    parents: dict[str, str] = {}
    children: dict[str, str] = {}
    terminal_disclaimer: bool | None = None


class BytesLedger:
    def __init__(self, path: Path) -> None:
        self.path: Path = path

    def _entries(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        loaded: list[dict[str, object]] = json.loads(self.path.read_text())
        return loaded

    def add(self, label: str, bytes_processed: int) -> None:
        entries: list[dict[str, object]] = self._entries()
        entries.append({"label": label, "bytes": bytes_processed, "at": utc_now().isoformat()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=1))

    def total(self) -> int:
        return sum(int(str(e["bytes"])) for e in self._entries())


def gcloud_token(account: str) -> str:
    gcloud: str | None = shutil.which("gcloud")
    if gcloud is None:
        msg = "GOOGLE_CLOUD_ACCOUNT is set but the gcloud CLI is not installed"
        raise RuntimeError(msg)
    done: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [gcloud, "auth", "print-access-token", f"--account={account}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


class GoogleQueryRunner:
    def __init__(self, project: str, account: str | None = None) -> None:
        from google.cloud import bigquery  # noqa: PLC0415  # slow import, only for live runs
        from google.oauth2.credentials import Credentials  # noqa: PLC0415

        self._bq = bigquery
        # A named account avoids touching Application Default Credentials, which other tools share.
        credentials: Credentials | None = (
            Credentials(gcloud_token(account)) if account else None  # type: ignore[no-untyped-call]
        )
        self._client = bigquery.Client(project=project, credentials=credentials)

    def _params(self, params: Mapping[str, object]) -> list[object]:
        out: list[object] = []
        for name, value in params.items():
            if isinstance(value, list):
                out.append(self._bq.ArrayQueryParameter(name, "STRING", [str(v) for v in value]))
            else:
                out.append(self._bq.ScalarQueryParameter(name, "STRING", str(value)))
        return out

    def dry_run(self, sql: str, params: Mapping[str, object]) -> int:
        config = self._bq.QueryJobConfig(
            dry_run=True, use_query_cache=False, query_parameters=self._params(params)
        )
        job = self._client.query(sql, job_config=config)
        return int(job.total_bytes_processed or 0)

    def run(self, sql: str, params: Mapping[str, object], max_bytes: int) -> tuple[list[Row], int]:
        config = self._bq.QueryJobConfig(
            maximum_bytes_billed=max_bytes, query_parameters=self._params(params)
        )
        job = self._client.query(sql, job_config=config)
        rows: list[Row] = [dict(r.items()) for r in job.result()]
        return rows, int(job.total_bytes_billed or 0)


def _jsonable(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def parse_dependent(value: str | None, text: str) -> int | None:
    if value not in (None, "", "-1", "NULL"):
        found: re.Match[str] | None = re.search(r"\d+", str(value))
        if found:
            return int(found[0])
    reference: re.Match[str] | None = _CLAIM_REF.search(text)
    return int(reference[1]) if reference else None


def _id(key: str) -> str:
    return key.removeprefix("US-")


def _doc_key(reldocno: str, relkind: str) -> str:
    if "grant" in relkind:
        try:
            return parse_patent_number(reldocno).key
        except IdentifierError:
            return f"patent {reldocno}"
    try:
        return f"application {parse_application_number(reldocno)}"
    except IdentifierError:
        return f"application {reldocno}"


class BigQueryGateway:
    def __init__(
        self,
        runner: QueryRunner | None,
        cache_dir: Path,
        ledger: BytesLedger,
        max_bytes_per_query: int = DEFAULT_MAX_BYTES,
        *,
        offline: bool = False,
    ) -> None:
        self._runner: QueryRunner | None = runner
        self._cache_dir: Path = cache_dir / "queries"
        self.ledger: BytesLedger = ledger
        self._max_bytes: int = max_bytes_per_query
        self._offline: bool = offline

    def query(self, sql: str, params: Mapping[str, object], label: str) -> list[Row]:
        digest: str = hashlib.sha256(
            (sql + json.dumps(params, sort_keys=True, default=str)).encode()
        ).hexdigest()
        path: Path = self._cache_dir / f"{digest}.json"
        if path.exists():
            cached: list[Row] = json.loads(path.read_text())
            return cached
        if self._offline or self._runner is None:
            msg = f"no cached result for BigQuery query '{label}' and the run is offline"
            raise CacheMissError(msg)
        estimate: int = self._runner.dry_run(sql, params)
        if estimate > self._max_bytes:
            msg = f"query '{label}' would scan {estimate:,} bytes, over the {self._max_bytes:,} cap"
            raise BigQueryBudgetError(msg)
        rows, billed = self._runner.run(sql, params, self._max_bytes)
        self.ledger.add(label, billed)
        clean: list[Row] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(clean))
        return clean

    def discover(
        self, cpc_prefixes: Sequence[str], grant_from: date, grant_to: date
    ) -> list[PatentRecord]:
        params: dict[str, object] = {
            "prefixes": list(cpc_prefixes),
            "grant_from": grant_from.isoformat(),
            "grant_to": grant_to.isoformat(),
        }
        rows: list[Row] = self.query(DISCOVERY_SQL, params, "discovery")
        return [to_patent_record(row) for row in rows]

    def claims(self, keys: Sequence[str]) -> dict[str, list[ClaimRecord]]:
        rows: list[Row] = self.query(CLAIMS_SQL, {"ids": [_id(k) for k in keys]}, "claims")
        grouped: dict[str, list[ClaimRecord]] = {}
        for row in rows:
            key: str = f"US-{row['patent_id']}"
            text: str = str(row.get("text") or "")
            sequence: int = int(str(row["sequence"]))
            dependent: int | None = parse_dependent(
                None if row.get("dependent") is None else str(row["dependent"]), text
            )
            grouped.setdefault(key, []).append(
                ClaimRecord(patent_key=key, sequence=sequence, text=text, dependent_on=dependent)
            )
        return {k: sorted(v, key=lambda c: c.sequence) for k, v in grouped.items()}

    def forward_citations(self, keys: Sequence[str]) -> dict[str, list[str]]:
        rows: list[Row] = self.query(CITATIONS_SQL, {"ids": [_id(k) for k in keys]}, "citations")
        cites: dict[str, list[str]] = {}
        for row in rows:
            cites.setdefault(f"US-{row['citation_id']}", []).append(f"US-{row['patent_id']}")
        return cites

    def continuity(self, keys: Sequence[str]) -> dict[str, Continuity]:
        rows: list[Row] = self.query(CONTINUITY_SQL, {"ids": [_id(k) for k in keys]}, "continuity")
        info: dict[str, Continuity] = {}
        for row in rows:
            key: str = f"US-{row['patent_id']}"
            entry: Continuity = info.setdefault(key, Continuity())
            disclaimer: object = row.get("term_disclaimer")
            if disclaimer:
                entry.terminal_disclaimer = True
            elif entry.terminal_disclaimer is None:
                entry.terminal_disclaimer = False
            doctype: object = row.get("doctype")
            if not isinstance(doctype, str) or doctype not in _RELATIONS:
                continue
            relkind: str = str(row.get("relkind") or "")
            doc: str = _doc_key(str(row.get("reldocno") or ""), relkind)
            target: dict[str, str] = (
                entry.children if relkind.startswith("child") else entry.parents
            )
            target[doc] = _RELATIONS[doctype]
        return info


def to_patent_record(row: Mapping[str, object]) -> PatentRecord:
    patent_id: str = str(row["id"])
    kind: str = str(row.get("kind") or "")
    grant: date = date.fromisoformat(str(row["date"]))
    filing_raw: object = row.get("filing_date")
    cpc: object = row.get("cpc") or []
    assignees: object = row.get("assignees") or []
    return PatentRecord(
        patent=parse_patent_number(f"US-{patent_id}-{kind}" if kind else patent_id),
        title=str(row.get("title") or ""),
        grant_date=grant,
        filing_date=date.fromisoformat(str(filing_raw)) if filing_raw else grant,
        kind=kind,
        num_claims=int(str(row.get("num_claims") or 0)),
        cpc_codes=[str(c) for c in cpc] if isinstance(cpc, list) else [],
        assignees=[str(a) for a in assignees if a] if isinstance(assignees, list) else [],
    )
