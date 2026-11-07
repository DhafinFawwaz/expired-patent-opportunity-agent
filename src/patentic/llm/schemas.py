from typing import Literal

from pydantic import BaseModel

StructuredMethod = Literal["json_schema", "json_mode", "function_calling"]


class PlanDraft(BaseModel):
    search_terms: list[str]
    cpc_codes: list[str]
    exclusion_terms: list[str]
    sources: list[str]
    screening_criteria: list[str]
    output_structure: list[str]


class TechnicalSummary(BaseModel):
    summary: str
    mechanism: str
    key_claim_elements: list[str]
    implementation_unknowns: list[str]
    powered: Literal["non_powered", "powered", "unclear"]
    evidence_ids: list[str]
    quotes: list[str]


class OpportunityRationale(BaseModel):
    commercial_relevance: int
    engineering_effort: int
    applications: list[str]
    challenges: list[str]
    rationale: str
    evidence_ids: list[str]


class ProseSection(BaseModel):
    section: str
    text: str


class TechnicalContext(BaseModel):
    patent_key: str
    title: str
    abstract_or_first_claim: str
    text: str
    evidence_ids: list[str]


class OpportunityContext(BaseModel):
    patent_key: str
    title: str
    summary: str
    status: str
    evidence_ids: list[str]
    category: str = "non-powered household cleaning tools"
    intended_product: str = ""


class CallMeta(BaseModel):
    call: str
    model: str
    method: StructuredMethod | Literal["fallback", "default"]
    attempts: int
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
