import json
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from patentic.adapters.base import EvidenceRecord
from patentic.adapters.fixtures import FixtureCase
from patentic.domain.request import ResearchRequest
from patentic.domain.status_rules import StatusAssessment
from patentic.llm.schemas import OpportunityRationale, PlanDraft, TechnicalSummary

SCHEMAS: Final[dict[str, type[BaseModel]]] = {
    "research-request": ResearchRequest,
    "evidence-record": EvidenceRecord,
    "status-assessment": StatusAssessment,
    "fixture-case": FixtureCase,
    "plan-draft": PlanDraft,
    "technical-summary": TechnicalSummary,
    "opportunity-rationale": OpportunityRationale,
}


def export_schemas(out_dir: Path, extra: dict[str, type[BaseModel]] | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in {**SCHEMAS, **(extra or {})}.items():
        path: Path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written
