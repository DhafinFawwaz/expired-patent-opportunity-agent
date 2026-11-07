import json
import re
from collections.abc import Callable, Mapping, Sequence
from importlib import resources
from typing import Any, Final, TypeVar

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel

from patentic.config.settings import Settings
from patentic.domain.request import ResearchRequest
from patentic.llm.fallbacks import (
    opportunity_neutral,
    plan_from_template,
    prose_templated,
    technical_extractive,
)
from patentic.llm.schemas import (
    CallMeta,
    OpportunityContext,
    OpportunityRationale,
    PlanDraft,
    ProseSection,
    StructuredMethod,
    TechnicalContext,
    TechnicalSummary,
)

T = TypeVar("T", bound=BaseModel)
Structured = Runnable[LanguageModelInput, dict[str, Any] | BaseModel]
MAX_TOKENS: Final[int] = 4096
ATTEMPTS: Final[int] = 2
EM_DASH: Final[str] = "\u2014"
EN_DASH: Final[str] = "\u2013"
_SPACE: Final[re.Pattern[str]] = re.compile(r"\s+")


def _prompt(name: str) -> tuple[str, str]:
    text: str = resources.files("patentic.llm.prompts").joinpath(f"{name}.md").read_text("utf-8")
    system, human = text.split("## human", 1)
    return system.replace("## system", "", 1).strip(), human.strip()


def _norm(text: str) -> str:
    return _SPACE.sub(" ", text).strip().lower()


def _model_name(model: BaseChatModel) -> str:
    for attr in ("model_name", "model"):
        value: object = getattr(model, attr, None)
        if isinstance(value, str) and value:
            return value
    return type(model).__name__


def _retryable() -> tuple[type[BaseException], ...]:
    from litellm import exceptions  # noqa: PLC0415  # heavy; only when a real model is used

    return (
        exceptions.RateLimitError,
        exceptions.Timeout,
        exceptions.APIConnectionError,
        exceptions.InternalServerError,
        exceptions.ServiceUnavailableError,
    )


class LlmCaller:
    def __init__(
        self,
        tools_model: BaseChatModel,
        prose_model: BaseChatModel,
        method: StructuredMethod | None,
        usage: UsageMetadataCallbackHandler,
    ) -> None:
        self._tools: BaseChatModel = tools_model
        self._prose: BaseChatModel = prose_model
        self._method: StructuredMethod | None = method
        self.usage: UsageMetadataCallbackHandler = usage

    def plan(self, request: ResearchRequest, feedback: Sequence[str]) -> tuple[PlanDraft, CallMeta]:
        system, human = _prompt("plan")
        prompt: str = human.format(
            technology_category=request.technology_category,
            intended_product=request.intended_product,
            commercial_constraints="; ".join(request.commercial_constraints) or "none given",
            feedback="; ".join(feedback) or "none",
        )
        result, meta = self._structured(
            self._tools, PlanDraft, system, prompt, "plan", lambda _p: None
        )
        return (result or plan_from_template(request)), meta

    def technical(self, ctx: TechnicalContext) -> tuple[TechnicalSummary, CallMeta]:
        system, human = _prompt("technical")
        prompt: str = human.format(
            patent_key=ctx.patent_key,
            title=ctx.title,
            evidence_ids=", ".join(ctx.evidence_ids),
            text=ctx.text,
        )
        source: str = _norm(ctx.text)

        def check(summary: TechnicalSummary) -> str | None:
            unknown: list[str] = [e for e in summary.evidence_ids if e not in ctx.evidence_ids]
            if unknown:
                return f"evidence ids not in the list: {unknown}"
            missing: list[str] = [q for q in summary.quotes if _norm(q) not in source]
            if missing:
                return f"quotes not found word for word in the fetched text: {missing}"
            return None

        result, meta = self._structured(
            self._tools, TechnicalSummary, system, prompt, f"technical:{ctx.patent_key}", check
        )
        return (result or technical_extractive(ctx)), meta

    def opportunity(self, ctx: OpportunityContext) -> tuple[OpportunityRationale, CallMeta]:
        system, human = _prompt("opportunity")
        prompt: str = human.format(
            category=ctx.category,
            intended_product=ctx.intended_product or "not specified",
            patent_key=ctx.patent_key,
            title=ctx.title,
            status=ctx.status,
            evidence_ids=", ".join(ctx.evidence_ids),
            summary=ctx.summary,
        )
        result, meta = self._structured(
            self._tools,
            OpportunityRationale,
            system,
            prompt,
            f"opportunity:{ctx.patent_key}",
            lambda _r: None,
        )
        if result is None:
            return opportunity_neutral(ctx), meta
        clamped: OpportunityRationale = result.model_copy(
            update={
                "commercial_relevance": max(1, min(5, result.commercial_relevance)),
                "engineering_effort": max(1, min(5, result.engineering_effort)),
                "evidence_ids": [e for e in result.evidence_ids if e in ctx.evidence_ids],
                "rationale": _clean(result.rationale, 200),
            }
        )
        return clamped, meta

    def prose(
        self, section: str, ctx: Mapping[str, object], word_budget: int
    ) -> tuple[ProseSection, CallMeta]:
        system, human = _prompt("prose")
        data: str = json.dumps(
            {k: v for k, v in ctx.items() if k not in {"fallback", "brief"}}, default=str, indent=1
        )
        prompt: str = human.format(section=section, brief=ctx.get("brief", ""), data=data)
        result, meta = self._structured(
            self._prose,
            ProseSection,
            system.format(word_budget=word_budget),
            prompt,
            f"prose:{section}",
            lambda _p: None,
        )
        if result is None or not result.text.strip():
            return prose_templated(section, ctx), meta
        return ProseSection(section=section, text=_clean(result.text, word_budget)), meta

    def _structured(
        self,
        model: BaseChatModel,
        schema: type[T],
        system: str,
        prompt: str,
        call: str,
        check: Callable[[T], str | None],
    ) -> tuple[T | None, CallMeta]:
        kwargs: dict[str, object] = {"method": self._method} if self._method else {}
        runnable: Structured = model.with_structured_output(schema, include_raw=True, **kwargs)
        if self._method:
            runnable = runnable.with_retry(
                retry_if_exception_type=_retryable(), stop_after_attempt=3
            )
        config: RunnableConfig = {
            "callbacks": [self.usage],
            "run_name": call,
            "tags": ["patentic", call.split(":", 1)[0]],
        }
        meta: CallMeta = CallMeta(
            call=call, model=_model_name(model), method=self._method or "default", attempts=0
        )
        messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(prompt)]
        for _ in range(ATTEMPTS):
            meta.attempts += 1
            try:
                result: dict[str, Any] | BaseModel = runnable.invoke(messages, config=config)
            except Exception as exc:  # noqa: BLE001  # free providers fail in many ways; we fall back
                meta.last_error = f"{type(exc).__name__}: {exc}"[:300]
                messages = [*messages, HumanMessage(f"The last attempt failed: {exc}. Try again.")]
                continue
            out: dict[str, Any] = result if isinstance(result, dict) else {"parsed": result}
            _account(meta, out.get("raw"))
            parsed: object = out.get("parsed")
            if parsed is None:
                problem: str = str(out.get("parsing_error") or "no structured output was returned")
                meta.last_error = problem[:300]
                messages = [
                    *messages,
                    HumanMessage(f"Your answer was invalid: {problem}. Answer again."),
                ]
                continue
            candidate: T = schema.model_validate(
                parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
            )
            issue: str | None = check(candidate)
            if issue is None:
                return candidate, meta
            meta.last_error = issue[:300]
            messages = [*messages, HumanMessage(f"Your answer was invalid: {issue}. Answer again.")]
        meta.method = "fallback"
        return None, meta


def _account(meta: CallMeta, raw: object) -> None:
    usage: object = getattr(raw, "usage_metadata", None)
    if isinstance(usage, dict):
        meta.tokens_in += int(usage.get("input_tokens", 0))
        meta.tokens_out += int(usage.get("output_tokens", 0))
    metadata: object = getattr(raw, "response_metadata", None)
    if isinstance(metadata, dict):
        cost: object = metadata.get("response_cost")
        if isinstance(cost, (int, float)):
            meta.cost_usd += float(cost)


def _clean(text: str, word_budget: int) -> str:
    cleaned: str = text.replace(EM_DASH, ", ").replace(EN_DASH, "-").replace(" , ", ", ")
    words: list[str] = cleaned.split()
    if len(words) <= word_budget:
        return cleaned.strip()
    cut: str = " ".join(words[:word_budget])
    end: int = cut.rfind(". ")
    return cut[: end + 1] if end > 0 else cut + "."


def build_models(settings: Settings) -> tuple[BaseChatModel, BaseChatModel]:
    if settings.llm_model:
        from langchain_litellm import ChatLiteLLM  # noqa: PLC0415

        paid: BaseChatModel = ChatLiteLLM(model=settings.llm_model, max_tokens=MAX_TOKENS)
        return paid, paid
    from freellm import get_chat_model  # noqa: PLC0415

    return (
        get_chat_model("free-tools", max_tokens=MAX_TOKENS),
        get_chat_model("free", max_tokens=MAX_TOKENS),
    )


class _Probe(BaseModel):
    ok: bool


def probe_structured(model: BaseChatModel) -> StructuredMethod | None:
    methods: tuple[StructuredMethod, ...] = ("json_schema", "function_calling", "json_mode")
    for method in methods:
        try:
            runnable: Structured = model.with_structured_output(
                _Probe, method=method, include_raw=True
            )
            result: dict[str, Any] | BaseModel = runnable.invoke(
                [HumanMessage('Reply with JSON {"ok": true}.')]
            )
        except Exception:  # noqa: BLE001, S112  # an unsupported method is expected here
            continue
        parsed: object = result.get("parsed") if isinstance(result, dict) else result
        if parsed is not None:
            return method
    return None
