import re
from collections.abc import Mapping
from typing import Final

from patentic.domain.request import ResearchRequest
from patentic.domain.screening import load_cpc_sets, load_power_terms
from patentic.llm.schemas import (
    OpportunityContext,
    OpportunityRationale,
    PlanDraft,
    ProseSection,
    TechnicalContext,
    TechnicalSummary,
)

MIN_WORD: Final[int] = 4


def plan_from_template(request: ResearchRequest) -> PlanDraft:
    words: list[str] = [
        w for w in re.split(r"[^a-z]+", request.technology_category.lower()) if len(w) >= MIN_WORD
    ]
    return PlanDraft(
        search_terms=[*words, "mop", "squeegee", "scrubber", "brush", "dust pan"],
        cpc_codes=load_cpc_sets().core,
        exclusion_terms=load_power_terms().terms,
        sources=[
            "USPTO Official Gazette expiration and reinstatement notices",
            "BigQuery PatentsView tables for bibliographic data, claims and citations",
            "EPO OPS legal events when credentials are configured",
        ],
        screening_criteria=[
            "listed as expired for nonpayment in the Gazette window",
            "core CPC hit and no powered co-classification",
            "no power source in an independent claim",
            "reinstatement lists scanned for every later week",
        ],
        output_structure=["Word report with ten sections", "PowerPoint deck with nine slides"],
    )


def technical_extractive(ctx: TechnicalContext) -> TechnicalSummary:
    first: str = ctx.abstract_or_first_claim.strip()
    elements: list[str] = [
        p.strip() for p in re.split(r"[;,]", first) if len(p.strip()) >= MIN_WORD
    ][:5]
    return TechnicalSummary(
        summary=f"{ctx.title}. First independent claim: {first[:300]}",
        mechanism="Not summarised; the model was unavailable.",
        key_claim_elements=elements,
        implementation_unknowns=["Needs a manual read of the full claims and drawings."],
        powered="unclear",
        evidence_ids=ctx.evidence_ids,
        quotes=[],
    )


def opportunity_neutral(ctx: OpportunityContext) -> OpportunityRationale:
    return OpportunityRationale(
        commercial_relevance=3,
        engineering_effort=3,
        applications=[],
        challenges=[],
        rationale="Model unavailable, so neutral scores were used; needs a manual assessment.",
        evidence_ids=ctx.evidence_ids,
    )


def prose_templated(section: str, ctx: Mapping[str, object]) -> ProseSection:
    fallback: object = ctx.get("fallback")
    text: str = fallback if isinstance(fallback, str) else "No text was generated for this section."
    return ProseSection(section=section, text=text)
