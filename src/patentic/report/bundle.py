from datetime import date, datetime
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from patentic.domain.confidence import SourceGrade
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import Source
from patentic.domain.related import RelatedRecord
from patentic.domain.request import ResearchRequest
from patentic.domain.scoring import Scores, ScoringWeights
from patentic.domain.status_rules import StatusAssessment
from patentic.llm.schemas import OpportunityRationale, PlanDraft, TechnicalSummary

LABEL: Final[str] = (
    "Research screening only. Not a legal opinion or freedom-to-operate determination."
)


class Reference(BaseModel):
    id: str
    title: str
    url: str
    retrieved: date


class TimelineRow(BaseModel):
    date: date
    event: str
    source: Source
    grade: SourceGrade
    evidence_id: str


class CandidateReport(BaseModel):
    key: str
    display: str
    title: str
    grant_date: date
    filing_date: date
    cpc_codes: list[str]
    status: StatusAssessment
    timeline: list[TimelineRow]
    technical: TechnicalSummary | None = None
    opportunity: OpportunityRationale | None = None
    related: list[RelatedRecord] = []
    flags: list[str] = []
    scores: Scores | None = None
    recommendation: Literal["Shortlist", "Hold", "Exclude"]
    reviewer_note: str | None = None
    is_synthetic: bool = False
    evidence_ids: list[str] = []


class FlowCounts(BaseModel):
    found: int
    expired_in_window: int
    passed_screening: int
    status_verified: int
    analysed: int
    not_analysed: int
    recommended: int


class RunInfo(BaseModel):
    thread_id: str
    created: datetime
    is_demo: bool
    model: str
    llm_calls: int
    fallback_calls: int
    bigquery_bytes: int
    outages: list[str]
    ops_configured: bool


class ReportBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    run: RunInfo
    request: ResearchRequest
    plan: PlanDraft
    coverage: ScanCoverage
    flow: FlowCounts
    candidates: list[CandidateReport]
    illustration: CandidateReport | None = None
    illustration_note: str = ""
    shortlist: list[str]
    weights: ScoringWeights
    prose: dict[str, str]
    methodology: list[str]
    key_assumptions: list[str]
    quality_of_information: list[str]
    limitations: list[str]
    references: list[Reference]
    label: str = LABEL

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        shortlisted: set[str] = {c.key for c in self.candidates if c.recommendation == "Shortlist"}
        if not set(self.shortlist) <= shortlisted:
            msg = "shortlist must name candidates recommended as Shortlist"
            raise ValueError(msg)
        if len(self.candidates) > self.request.max_candidates:
            msg = "more candidates than the request allows"
            raise ValueError(msg)
        if any(c.is_synthetic for c in self.candidates) and not self.run.is_demo:
            msg = "synthetic candidates may only appear in a demo run"
            raise ValueError(msg)
        refs: set[str] = {r.id for r in self.references}
        missing: set[str] = {e for c in self.candidates for e in c.evidence_ids} - refs
        if missing:
            msg = f"evidence without a reference entry: {sorted(missing)[:3]}"
            raise ValueError(msg)
        if self.label != LABEL:
            msg = "the screening label must not change"
            raise ValueError(msg)
        return self
