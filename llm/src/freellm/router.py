"""FreeLLM: ranks every free model you can reach and builds a LiteLLM Router over them.

Model groups in the router
  free          every usable free model, best first (LiteLLM ``order`` levels)
  free-tools    only models that are known or presumed to support tool calling
  free-vision   only models known to accept images
  free-fast     ranked by observed latency instead of quality
  <canonical>   one group per model (e.g. ``120b-gpt-oss``), spread over all providers/keys serving it
  <provider>/<model_id>   one group per exact deployment

Inside a group, every (provider, key) serving the same model shares an order level, so load is
spread across keys and providers; when a level fails (rate limit, outage, bad key) LiteLLM moves to
the next level. A failing deployment is cooled down for ``cooldown`` seconds.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

import litellm
from litellm import Router

from . import stats as stats_mod
from ._anon import ANON_KEY, install as install_anon_hook
from .catalog import ModelInfo, Provider, discover, load_providers
from .ranking import Ratings, canonical, score

log = logging.getLogger("freellm")

# Meta-routers / aliases whose quality can't be looked up.
DEFAULT_OVERRIDES = {"openrouter/free": 1300.0, "default": 1300.0}
GROUPS = ("free", "free-tools", "free-vision", "free-fast")


@dataclass
class Deployment:
    provider: Provider
    model: ModelInfo
    api_key: str | None
    key_index: int

    @property
    def key(self) -> str:
        h = hashlib.sha1((self.api_key or "anon").encode()).hexdigest()[:8]
        return f"{self.provider.id}:{self.model.model_id}:{h}"

    @property
    def exact_name(self) -> str:
        return f"{self.provider.id}/{self.model.model_id}"


def pretty_name(model_ids: list[str]) -> str:
    """Readable group name for a model served under several ids: the shortest bare id, lowercased."""
    bare = [i.split("/")[-1].split(":free")[0].removesuffix("-free").lower() for i in model_ids]
    return min(bare, key=lambda b: (len(b), b))


@dataclass
class RankedModel:
    canonical: str  # readable group name, e.g. "glm-5.3-flash"
    model_ids: list[str]
    rating: float
    rated: bool  # found on the LMArena leaderboard
    score: float
    tools: bool | None
    vision: bool | None
    context: int | None
    latency: float | None
    deployments: list[Deployment] = field(default_factory=list)

    @property
    def providers(self) -> list[str]:
        return sorted({d.provider.id for d in self.deployments})

    def as_row(self) -> dict[str, Any]:
        return {
            "model": self.canonical,
            "ids": ", ".join(sorted(set(self.model_ids))),
            "rating": round(self.rating),
            "rated": self.rated,
            "score": round(self.score),
            "providers": ",".join(self.providers),
            "keys": len(self.deployments),
            "tools": self.tools,
            "vision": self.vision,
            "context": self.context,
            "latency_s": self.latency,
        }


def _merge_flag(values: Iterable[bool | None]) -> bool | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return any(vals)


class FreeLLM:
    """Entry point.

    >>> from freellm import FreeLLM
    >>> fl = FreeLLM()
    >>> fl.chat_model().invoke("hello")          # LangChain chat model, best free model first
    >>> fl.complete("hello")                     # plain string in, string out
    >>> fl.ranked()[:5]                          # what will be tried, in order
    """

    def __init__(
        self,
        *,
        providers: Iterable[str] | None = None,
        exclude_providers: Iterable[str] = (),
        exclude_models: Iterable[str] = (),
        preference: str = "quality",
        top_n: int = 25,
        refresh: bool = False,
        rating_overrides: dict[str, float] | None = None,
        timeout: float = 60,
        cooldown: float = 60,
        catalog: dict[Provider, list[ModelInfo]] | None = None,
        arena_rows: list[dict] | None = None,
        record_stats: bool = True,
    ):
        """
        providers         only use these provider ids (default: all with a key, plus keyless ones)
        exclude_providers / exclude_models   skip these (model ids or canonical names)
        preference        "quality" (default), "balanced" or "speed"
        top_n             how many models the ``free*`` groups fall back through
        refresh           re-query provider /models lists and the leaderboard now
        rating_overrides  {model_id_or_canonical: rating} to force your own ranking
        timeout           per-request timeout (s); cooldown: how long a failing deployment is benched
        catalog / arena_rows   inject data (tests, offline use)
        """
        self.preference = preference
        self.top_n = top_n
        self.timeout = timeout
        self.cooldown = cooldown
        self.record_stats = record_stats
        self.exclude_models = {m.lower() for m in exclude_models}
        self.ratings = Ratings(arena_rows, {**DEFAULT_OVERRIDES, **(rating_overrides or {})})

        if catalog is None:
            all_p = load_providers()
            wanted = set(providers) if providers else None
            catalog = {}
            for pid, p in all_p.items():
                if wanted is not None and pid not in wanted:
                    continue
                if pid in set(exclude_providers) or not p.usable:
                    continue
                catalog[p] = discover(p, refresh=refresh)
        self._catalog = catalog
        self._router: Router | None = None
        self._ranked: list[RankedModel] | None = None

    # ------------------------------------------------------------------ ranking

    def deployments(self) -> list[Deployment]:
        out: list[Deployment] = []
        for p, models in self._catalog.items():
            for m in models:
                if m.model_id.lower() in self.exclude_models or canonical(m.model_id) in self.exclude_models:
                    continue
                for i, key in enumerate(p.credentials):
                    out.append(Deployment(p, m, key, i))
        return out

    def ranked(self, *, tools: bool = False, vision: bool = False, min_context: int | None = None,
               preference: str | None = None) -> list[RankedModel]:
        """Usable free models, best first. Filters: tools / vision capability, context size."""
        pref = preference or self.preference
        if self._ranked is None or pref != self.preference:
            ranked = self._rank(pref)
            if pref == self.preference:
                self._ranked = ranked
        else:
            ranked = self._ranked
        out = []
        for r in ranked:
            if tools and r.tools is False:
                continue
            if vision and not r.vision:
                continue
            if min_context and r.context and r.context < min_context:
                continue
            out.append(r)
        return out

    def _rank(self, preference: str) -> list[RankedModel]:
        st = stats_mod.load()
        groups: dict[str, list[Deployment]] = {}
        for d in self.deployments():
            groups.setdefault(canonical(d.model.model_id), []).append(d)
        ranked: list[RankedModel] = []
        for canon, deps in groups.items():
            ids = [d.model.model_id for d in deps]
            found = [self.ratings.lookup(i) for i in ids] + [self.ratings.lookup(canon)]
            known = [f for f in found if f is not None]
            rating = max(known) if known else self.ratings.rating(ids[0])
            dep_scores = [score(rating, st.get(d.key), preference) for d in deps]
            lats = [st[d.key]["latency"] for d in deps if st.get(d.key, {}).get("latency")]
            ctxs = [d.model.context for d in deps if d.model.context]
            ranked.append(
                RankedModel(
                    canonical=pretty_name(ids),
                    model_ids=ids,
                    rating=rating,
                    rated=bool(known),
                    score=max(dep_scores),
                    tools=_merge_flag(d.model.tools for d in deps),
                    vision=_merge_flag(d.model.vision for d in deps),
                    context=max(ctxs) if ctxs else None,
                    latency=min(lats) if lats else None,
                    deployments=[d for _, d in sorted(zip(dep_scores, deps), key=lambda x: -x[0])],
                )
            )
        if preference == "speed":
            # Unmeasured models go after measured fast ones but keep quality order among themselves.
            ranked.sort(key=lambda r: (r.latency is None, r.latency or 0, -r.score, r.canonical))
        else:
            ranked.sort(key=lambda r: (-r.score, r.canonical))  # name breaks ties: stable output
        return ranked

    def available(self) -> list[tuple[RankedModel, list[Deployment]]]:
        """Models with at least one deployment whose most recent call succeeded (see `freellm ping`).

        Deterministic: sorted by LMArena rating, then name; transient penalties are ignored.
        Returns (model, working deployments).
        """
        st = stats_mod.load()

        def works(d: Deployment) -> bool:
            s = st.get(d.key) or {}
            return bool(s.get("last_ok")) and s.get("last_ok", 0) >= s.get("last_fail", 0)

        out = [(r, [d for d in r.deployments if works(d)]) for r in self.ranked()]
        out = [(r, ds) for r, ds in out if ds]
        out.sort(key=lambda x: (-x[0].rating, x[0].canonical))
        return out

    # ------------------------------------------------------------------ router

    def _litellm_params(self, d: Deployment, order: int | None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": f"{d.provider.litellm_prefix}/{d.model.model_id}",
            "api_base": d.provider.resolved_api_base,
            # Anonymous: sentinel key whose Authorization header is stripped (see _anon.py).
            "api_key": d.api_key or ANON_KEY,
            "rpm": d.provider.rpm,
            "timeout": self.timeout,
        }
        if order is not None:
            params["order"] = order
        return params

    def _entry(self, group: str, d: Deployment, order: int | None) -> dict[str, Any]:
        return {
            "model_name": group,
            "litellm_params": self._litellm_params(d, order),
            "model_info": {
                "id": f"{group}|{d.key}",
                "freellm_key": d.key,
                "provider": d.provider.id,
                "canonical": canonical(d.model.model_id),
            },
        }

    def model_list(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        def add_ranked(group: str, models: list[RankedModel]) -> None:
            for level, r in enumerate(models[: self.top_n], start=1):
                for d in r.deployments:
                    entries.append(self._entry(group, d, level))

        add_ranked("free", self.ranked())
        add_ranked("free-tools", self.ranked(tools=True))
        add_ranked("free-vision", self.ranked(vision=True))
        add_ranked("free-fast", self.ranked(preference="speed"))
        for r in self.ranked():
            for d in r.deployments:
                entries.append(self._entry(r.canonical, d, None))
                entries.append(self._entry(d.exact_name, d, None))
        return entries

    @property
    def router(self) -> Router:
        if self._router is None:
            ml = self.model_list()
            if not ml:
                raise RuntimeError(
                    "freellm: no usable free models. Add an API key (run `freellm keys` for links) "
                    "or check your network."
                )
            install_anon_hook()
            self._router = Router(
                model_list=ml,
                num_retries=1,  # one retry inside a level picks another key/provider of the same model
                retry_after=0,
                allowed_fails=1,
                cooldown_time=self.cooldown,
                max_fallbacks=self.top_n + 1,
                timeout=self.timeout,
            )
            if self.record_stats and not any(isinstance(c, stats_mod.StatsCallback) for c in litellm.callbacks):
                litellm.callbacks.append(stats_mod.StatsCallback())
        return self._router

    def groups(self) -> list[str]:
        return sorted({e["model_name"] for e in self.model_list()})

    def resolve(self, model: str | None = None) -> str:
        """Map a user-facing model name to a router group ("free" by default)."""
        if not model:
            return "free"
        names = {e["model_name"] for e in self.router.model_list}
        if model in names:
            return model
        by_key = {canonical(i): r.canonical for r in self.ranked() for i in r.model_ids}
        if (c := by_key.get(canonical(model.split("/")[-1]))) and c in names:
            return c
        raise ValueError(f"freellm: unknown model {model!r}. Try one of: {', '.join(GROUPS)} or `freellm models`.")

    # ------------------------------------------------------------------ convenience

    def chat_model(self, model: str | None = None, **kwargs: Any):
        """A LangChain chat model (``ChatLiteLLMRouter``) backed by the router.

        ``model``: "free" (default), "free-tools", "free-vision", "free-fast", a canonical name,
        or "<provider>/<model_id>". Extra kwargs (temperature, max_tokens, ...) go to LangChain.
        """
        from langchain_litellm import ChatLiteLLMRouter

        group = self.resolve(model)
        return ChatLiteLLMRouter(router=self.router, model=group, model_name=group, **kwargs)

    def completion(self, messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any):
        """Raw LiteLLM completion (OpenAI-format response) through the router."""
        return self.router.completion(model=self.resolve(model), messages=messages, **kwargs)

    async def acompletion(self, messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any):
        return await self.router.acompletion(model=self.resolve(model), messages=messages, **kwargs)

    def complete(self, prompt: str, model: str | None = None, system: str | None = None, **kwargs: Any) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        resp = self.completion(msgs, model=model, **kwargs)
        return resp.choices[0].message.content or ""

    @staticmethod
    def served_by(response: Any) -> str | None:
        """Which deployment answered a LiteLLM response (``provider:model:keyhash``)."""
        hidden = getattr(response, "_hidden_params", {}) or {}
        mid = hidden.get("model_id") or ""
        return mid.split("|", 1)[-1] or None
