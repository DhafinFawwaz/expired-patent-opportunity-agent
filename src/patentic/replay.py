import gzip
import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from langchain_core.callbacks import UsageMetadataCallbackHandler
from pydantic import BaseModel

from patentic.domain.request import ResearchRequest
from patentic.llm.calls import LlmCaller
from patentic.llm.null_model import NullChatModel
from patentic.llm.schemas import (
    CallMeta,
    OpportunityContext,
    OpportunityRationale,
    PlanDraft,
    ProseSection,
    TechnicalContext,
    TechnicalSummary,
)

REPLAY_DIR: Final[Path] = Path("fixtures") / "replay"
PACKED: Final[tuple[str, ...]] = ("http", "bq")


class Provenance(BaseModel):
    thread_id: str
    today: date
    request: dict[str, object]
    commit: str
    bigquery_bytes: int
    candidates: list[tuple[str, str]]


class Recorded(BaseModel):
    plan: PlanDraft | None = None
    technical: dict[str, TechnicalSummary] = {}
    opportunity: dict[str, OpportunityRationale] = {}
    prose: dict[str, str] = {}


class ReplayCaller(LlmCaller):
    """Answers with the model outputs recorded in the live run; templates cover anything else."""

    def __init__(self, recorded: Recorded) -> None:
        null: NullChatModel = NullChatModel()
        super().__init__(null, null, None, UsageMetadataCallbackHandler())
        self._recorded: Recorded = recorded

    @staticmethod
    def _meta(call: str) -> CallMeta:
        return CallMeta(call=call, model="replay", method="default", attempts=0)

    def plan(self, request: ResearchRequest, feedback: Sequence[str]) -> tuple[PlanDraft, CallMeta]:
        if self._recorded.plan is None:
            return super().plan(request, feedback)
        return self._recorded.plan, self._meta("plan")

    def technical(self, ctx: TechnicalContext) -> tuple[TechnicalSummary, CallMeta]:
        found: TechnicalSummary | None = self._recorded.technical.get(ctx.patent_key)
        if found is None:
            return super().technical(ctx)
        return found, self._meta(f"technical:{ctx.patent_key}")

    def opportunity(self, ctx: OpportunityContext) -> tuple[OpportunityRationale, CallMeta]:
        found: OpportunityRationale | None = self._recorded.opportunity.get(ctx.patent_key)
        if found is None:
            return super().opportunity(ctx)
        return found, self._meta(f"opportunity:{ctx.patent_key}")

    def prose(
        self, section: str, ctx: Mapping[str, object], word_budget: int
    ) -> tuple[ProseSection, CallMeta]:
        text: str | None = self._recorded.prose.get(section)
        if text is None:
            return super().prose(section, ctx, word_budget)
        return ProseSection(section=section, text=text), self._meta(f"prose:{section}")


def pack(cache_dir: Path, out_dir: Path, provenance: Provenance, recorded: Recorded) -> None:
    files: dict[str, str] = {
        path.relative_to(cache_dir).as_posix(): path.read_text()
        for top in PACKED
        for path in sorted((cache_dir / top).rglob("*.json"))
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the archive byte-identical across rebuilds.
    with gzip.GzipFile(out_dir / "cache.json.gz", "wb", mtime=0) as archive:
        archive.write(json.dumps(files, sort_keys=True).encode())
    (out_dir / "provenance.json").write_text(provenance.model_dump_json(indent=2) + "\n")
    (out_dir / "llm.json").write_text(recorded.model_dump_json(indent=2) + "\n")


def unpack(replay_dir: Path, cache_dir: Path) -> Provenance:
    with gzip.open(replay_dir / "cache.json.gz", "rb") as archive:
        files: dict[str, str] = json.loads(archive.read())
    for name, text in files.items():
        target: Path = cache_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return Provenance.model_validate_json((replay_dir / "provenance.json").read_text())


def load_recorded(replay_dir: Path) -> Recorded:
    return Recorded.model_validate_json((replay_dir / "llm.json").read_text())
