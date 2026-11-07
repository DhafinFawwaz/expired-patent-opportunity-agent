import pytest
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage

from patentic.config.settings import Settings
from patentic.domain.request import ResearchRequest
from patentic.llm.calls import LlmCaller, build_models, probe_structured
from patentic.llm.schemas import (
    CallMeta,
    OpportunityContext,
    OpportunityRationale,
    PlanDraft,
    ProseSection,
    TechnicalContext,
    TechnicalSummary,
)
from tests.llm.fakes import ScriptedChatModel, scripted, tool_reply

REQUEST: ResearchRequest = ResearchRequest(
    technology_category="non-powered household cleaning tools",
    intended_product="a manual mop or brush for home use",
)
PLAN_ARGS: dict[str, object] = {
    "search_terms": ["mop", "squeegee"],
    "cpc_codes": ["A47L13/"],
    "exclusion_terms": ["motor"],
    "sources": ["Official Gazette"],
    "screening_criteria": ["no powered co-class"],
    "output_structure": ["report", "deck"],
}
CLAIMS: str = "1. A mop head comprising a frame and a scrubbing pad on a second face of the frame."
TECH_CTX: TechnicalContext = TechnicalContext(
    patent_key="US-9999901",
    title="Mop head with reversible scrubbing pad",
    abstract_or_first_claim=CLAIMS,
    text=CLAIMS,
    evidence_ids=["ev1"],
)
TECH_ARGS: dict[str, object] = {
    "summary": "A reversible mop head.",
    "mechanism": "Two pads on opposite faces of one frame.",
    "key_claim_elements": ["frame", "scrubbing pad"],
    "implementation_unknowns": ["pad attachment"],
    "powered": "non_powered",
    "evidence_ids": ["ev1"],
    "quotes": ["a scrubbing pad on a second face"],
}


def caller(tools: ScriptedChatModel, prose: ScriptedChatModel | None = None) -> LlmCaller:
    return LlmCaller(tools, prose or scripted(), None, UsageMetadataCallbackHandler())


def test_plan_uses_structured_output() -> None:
    plan, meta = caller(scripted(tool_reply(PlanDraft, PLAN_ARGS))).plan(REQUEST, [])
    assert isinstance(plan, PlanDraft)
    assert plan.cpc_codes == ["A47L13/"]
    assert meta.method != "fallback"
    assert meta.tokens_in == 120


def test_plan_falls_back_to_template_on_parse_failure() -> None:
    model: ScriptedChatModel = scripted(
        AIMessage(content="not json"), AIMessage(content="still not")
    )
    plan, meta = caller(model).plan(REQUEST, ["fewer brushes"])
    assert meta.method == "fallback"
    assert "A47L13/" in plan.cpc_codes
    assert meta.attempts == 2


def test_technical_rejects_quote_not_in_text_then_falls_back() -> None:
    bad: dict[str, object] = {**TECH_ARGS, "quotes": ["a motor drives the pad"]}
    model: ScriptedChatModel = scripted(
        tool_reply(TechnicalSummary, bad), tool_reply(TechnicalSummary, bad)
    )
    summary, meta = caller(model).technical(TECH_CTX)
    assert meta.method == "fallback"
    assert summary.powered == "unclear"
    assert summary.evidence_ids == ["ev1"]


def test_technical_accepts_valid_quotes_after_one_reask() -> None:
    bad: dict[str, object] = {**TECH_ARGS, "evidence_ids": ["made-up"]}
    model: ScriptedChatModel = scripted(
        tool_reply(TechnicalSummary, bad), tool_reply(TechnicalSummary, TECH_ARGS)
    )
    summary, meta = caller(model).technical(TECH_CTX)
    assert summary.powered == "non_powered"
    assert meta.attempts == 2


def test_quote_check_ignores_case_and_spacing() -> None:
    loose: dict[str, object] = {**TECH_ARGS, "quotes": ["A  SCRUBBING pad on a second\nface"]}
    summary, _ = caller(scripted(tool_reply(TechnicalSummary, loose))).technical(TECH_CTX)
    assert summary.powered == "non_powered"


def test_opportunity_scores_clamped() -> None:
    args: dict[str, object] = {
        "commercial_relevance": 9,
        "engineering_effort": 0,
        "applications": ["home mops"],
        "challenges": ["tooling"],
        "rationale": "Cheap to make.",
        "evidence_ids": ["ev1"],
    }
    ctx: OpportunityContext = OpportunityContext(
        patent_key="US-9999901",
        title="t",
        summary="s",
        status="expired_nonpayment",
        evidence_ids=["ev1"],
    )
    result, _ = caller(scripted(tool_reply(OpportunityRationale, args))).opportunity(ctx)
    assert (result.commercial_relevance, result.engineering_effort) == (5, 1)


def test_prose_respects_word_budget_and_strips_em_dashes() -> None:
    long_text: str = "This tool works well \u2014 it is cheap. " * 40
    prose_model: ScriptedChatModel = scripted(
        tool_reply(ProseSection, {"section": "summary", "text": long_text})
    )
    section, _ = caller(scripted(), prose_model).prose("summary", {"fallback": "x"}, 50)
    assert len(section.text.split()) <= 60
    assert "\u2014" not in section.text


def test_prose_falls_back_to_supplied_text() -> None:
    section, meta = caller(scripted(), scripted("garbage", "garbage")).prose(
        "summary", {"fallback": "Two candidates were found."}, 50
    )
    assert section.text == "Two candidates were found."
    assert meta.method == "fallback"


def test_build_models_honours_llm_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    settings: Settings = Settings(llm_model="openai/gpt-test", _env_file=None)
    tools, prose = build_models(settings)
    assert getattr(tools, "model", None) == "openai/gpt-test"
    assert getattr(prose, "model", None) == "openai/gpt-test"


def test_probe_returns_none_when_model_raises() -> None:
    assert probe_structured(scripted()) is None


def test_call_meta_records_cost() -> None:
    _, meta = caller(scripted(tool_reply(PlanDraft, PLAN_ARGS))).plan(REQUEST, [])
    assert isinstance(meta, CallMeta)
    assert meta.cost_usd == 0.0


def test_fallback_records_the_last_problem() -> None:
    bad: dict[str, object] = {**TECH_ARGS, "quotes": ["a motor drives the pad"]}
    model: ScriptedChatModel = scripted(
        tool_reply(TechnicalSummary, bad), tool_reply(TechnicalSummary, bad)
    )
    _, meta = caller(model).technical(TECH_CTX)
    assert meta.last_error is not None
    assert "a motor drives the pad" in meta.last_error


def test_technical_accepts_quotes_wrapped_in_json_punctuation() -> None:
    wrapped: dict[str, object] = {**TECH_ARGS, "quotes": ['"a scrubbing pad on a second face",']}
    summary, meta = caller(scripted(tool_reply(TechnicalSummary, wrapped))).technical(TECH_CTX)
    assert meta.method != "fallback"
    assert summary.quotes == ["a scrubbing pad on a second face"]
