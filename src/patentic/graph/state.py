import operator
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from patentic.adapters.base import ClaimRecord, EvidenceRecord, PatentRecord
from patentic.domain.coverage import ScanCoverage
from patentic.domain.events import StatusEvent
from patentic.domain.related import RelatedRecord
from patentic.domain.request import ResearchRequest
from patentic.domain.scoring import Scores
from patentic.domain.status_rules import StatusAssessment
from patentic.graph.reducers import append_unique, merge_dict, override
from patentic.llm.schemas import CallMeta, OpportunityRationale, PlanDraft, TechnicalSummary

Recommendation = Literal["Shortlist", "Hold", "Exclude", "NotAnalysed"]


class ApprovalDecision(BaseModel):
    action: Literal["approve", "revise", "abort"]
    feedback: str | None = None


class ReviewDecision(BaseModel):
    action: Literal["accept", "edit", "abort"]
    keep: list[str] = []
    drop: list[str] = []
    flag: dict[str, str] = {}
    shortlist: list[str] = Field(default=[], max_length=2)


class ScreeningResult(BaseModel):
    core_hit: bool
    tier1_rejects: list[str] = []
    tier2_hits: list[str] = []
    tier3: Literal["non_powered", "powered", "unclear"] | None = None
    passed: bool


class Candidate(BaseModel):
    key: str
    record: PatentRecord
    assessment: StatusAssessment | None = None
    screening: ScreeningResult
    technical: TechnicalSummary | None = None
    opportunity: OpportunityRationale | None = None
    related: list[RelatedRecord] = []
    flags: list[str] = []
    scores: Scores | None = None
    recommendation: Recommendation | None = None
    reviewer_note: str | None = None
    is_synthetic: bool = False


class RunMeta(BaseModel):
    thread_id: str
    started_at: datetime
    model: str = "unknown"
    method: str = "default"
    is_demo: bool = False


class PipelineState(TypedDict, total=False):
    request: ResearchRequest
    stage: str
    plan: PlanDraft
    plan_feedback: Annotated[list[str], override]
    revisions: int
    approval: ApprovalDecision
    coverage: ScanCoverage
    records: Annotated[dict[str, PatentRecord], merge_dict]
    claims: Annotated[dict[str, list[ClaimRecord]], merge_dict]
    events: Annotated[dict[str, list[StatusEvent]], merge_dict]
    candidates: Annotated[dict[str, Candidate], merge_dict]
    evidence: Annotated[dict[str, EvidenceRecord], merge_dict]
    pool: list[str]
    review: ReviewDecision
    bundle_path: str
    calls: Annotated[list[CallMeta], operator.add]
    outages: Annotated[list[str], append_unique]
    run_meta: RunMeta


class InputState(TypedDict):
    request: ResearchRequest
