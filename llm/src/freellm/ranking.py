"""Model quality ranking.

Quality comes from the public LMArena text leaderboard
(HF dataset ``lmarena-ai/leaderboard-dataset``, no key, cached 24h). Provider model ids are
matched to arena display names by normalising both into token sets.

The final score blends that rating with what freellm has observed locally
(success rate, recent rate limits, latency) — see :func:`score`.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any

import httpx

from . import config

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("freellm")

ARENA_URL = "https://datasets-server.huggingface.co/rows"
ARENA_TTL = 24 * 3600
DEFAULT_RATING = 1250.0  # unknown models rank below well-known mid-tier models

# Tokens that don't change which model it is.
_STOP = {
    "instruct",
    "it",
    "chat",
    "versatile",
    "preview",
    "free",
    "latest",
    "fp8",
    "fp16",
    "bf16",
    "nvfp4",
    "hf",
    "fast",
    "turbo",
    "exp",
    "experimental",
    "model",
    "base",
    "online",
    "highspeed",
    "thinking",
    "non",
    "instant",
    "a",
    "the",
    "and",
    "v1",
    "beta",
}
# Organisation names that some providers prefix onto ids.
_ORGS = {
    "meta",
    "llama",
    "openai",
    "google",
    "nvidia",
    "qwen",
    "deepseek",
    "ai",
    "deepseekai",
    "mistralai",
    "moonshotai",
    "moonshot",
    "zai",
    "z",
    "zhipu",
    "thudm",
    "minimax",
    "minimaxai",
    "xiaomi",
    "cf",
    "microsoft",
    "ibm",
    "cohere",
    "coherelabs",
    "stepfun",
    "baidu",
    "alibaba",
    "tencent",
    "liquid",
    "nousresearch",
    "allenai",
    "bytedance",
    "xai",
    "x",
    "amazon",
    "anthropic",
    "org",
}


_SIZE = re.compile(r"a?\d+(\.\d+)?[bm]|e\d+b|\d+e")  # 24b, a17b, 128e, e4b
_VER = re.compile(r"\d+(\.\d+)*")


def tokens(name: str) -> frozenset[str]:
    """Normalise a model id or display name into comparable tokens."""
    s = name.lower()
    s = (
        s.split(":")[0] if not re.search(r":\d", s) else s.replace(":", "-")
    )  # "gpt-oss:20b" -> gpt-oss-20b
    s = re.sub(r"\([^)]*\)", " ", s)  # "(High)", "(Thinking)" qualifiers
    s = s.replace("@cf/", "")
    s = re.sub(r"\b(fp8|fp16|bf16|nvfp4|int4|int8|awq|gguf)\b", " ", s)
    s = re.sub(r"[-_ ](minimal|low|high|xhigh|max)$", " ", s)  # reasoning-effort suffixes
    s = re.sub(r"(?<=\d)_(?=\d)", ".", s)  # Llama-3_3 -> 3.3
    s = re.sub(r"-(20\d{2})-?(\d{2})(-?\d{2})?\b", " ", s)  # date suffixes
    s = re.sub(r"\b\d{4}\b", " ", s)  # 0905, 2507 style version stamps
    s = re.sub(r"(?<=[a-z])(?=\d)", " ", s)  # qwen3.5 -> qwen 3.5, llama3.1 -> llama 3.1
    toks = [t for t in re.split(r"[^a-z0-9.]+", s) if t and t != "."]
    toks = [t.strip(".") for t in toks]
    return frozenset(t for t in toks if t and t not in _STOP)


def canonical(model_id: str) -> str:
    """A provider-independent name used to group the same model across providers."""
    base = model_id.rsplit("/", maxsplit=1)[-1]
    return "-".join(sorted(tokens(base))) or model_id


# --------------------------------------------------------------------------- LMArena


def _arena_cache() -> Path:
    return config.cache_dir() / "arena_text.json"


def fetch_arena(refresh: bool = False) -> list[dict[str, Any]]:
    """Overall LMArena text rows: [{model_name, rating, rank, ...}]. Cached; [] when offline."""
    cp = _arena_cache()
    if not refresh and cp.exists():
        data: dict[str, Any] = json.loads(cp.read_text())
        if time.time() - data.get("ts", 0) < ARENA_TTL:
            cached: list[dict[str, Any]] = data["rows"]
            return cached
    rows: list[dict[str, Any]] = []
    try:
        for offset in range(0, 2000, 100):
            r = httpx.get(
                ARENA_URL,
                params={
                    "dataset": "lmarena-ai/leaderboard-dataset",
                    "config": "text",
                    "split": "latest",
                    "offset": offset,
                    "length": 100,
                },
                timeout=30,
            )
            r.raise_for_status()
            batch = [x["row"] for x in r.json().get("rows", [])]
            overall = [x for x in batch if x.get("category") == "overall"]
            rows.extend(overall)
            if len(overall) < len(batch) or not batch:
                break  # rows are sorted by category; overall comes first
    except Exception as e:
        log.warning("freellm: LMArena fetch failed (%s); using cached/default ratings", e)
        if cp.exists():
            stale: list[dict[str, Any]] = json.loads(cp.read_text())["rows"]
            return stale
        return []
    keep = [
        {"model_name": x["model_name"], "rating": x["rating"], "rank": x.get("rank")} for x in rows
    ]
    cp.write_text(json.dumps({"ts": time.time(), "rows": keep}))
    return keep


class Ratings:
    """Looks up an arena rating for any provider model id."""

    def __init__(
        self, rows: list[dict[str, Any]] | None = None, overrides: dict[str, float] | None = None
    ):
        rows = fetch_arena() if rows is None else rows
        self.by_tokens: dict[frozenset[str], float] = {}
        for r in rows:
            t = tokens(r["model_name"])
            if t:
                self.by_tokens[t] = max(self.by_tokens.get(t, 0.0), float(r["rating"]))
        self.overrides = {k.lower(): v for k, v in (overrides or {}).items()}
        self._memo: dict[str, float | None] = {}

    def lookup(self, model_id: str) -> float | None:
        if model_id.lower() in self.overrides:
            return self.overrides[model_id.lower()]
        if model_id in self._memo:
            return self._memo[model_id]
        t = tokens(model_id.rsplit("/", maxsplit=1)[-1]) if "/" in model_id else tokens(model_id)
        result = self.by_tokens.get(t)
        core = t - _ORGS
        if result is None and core:
            # 1. extra organisation tokens on either side ("zai-glm-4.7" vs "GLM-4.7")
            same = [r for at, r in self.by_tokens.items() if at - _ORGS == core]
            if same:
                result = max(same)
        if result is None and core:
            # 2. one side has extra size tokens ("Mistral-Small-3.2-24B" vs "Mistral Small 3.2").
            #    Several candidates -> take the lowest rating (conservative).
            close = [
                r
                for at, r in self.by_tokens.items()
                if (d := (at - _ORGS) ^ core) and all(_SIZE.fullmatch(x) for x in d)
            ]
            if close:
                result = min(close)
        if "latest" in model_id.lower() and core:
            # 3. "-latest" aliases: best of the family ("mistral-medium-latest" -> newest Mistral Medium)
            fam = [
                r
                for at, r in self.by_tokens.items()
                if core <= at and all(_VER.fullmatch(x) for x in at - core - _ORGS)
            ]
            if fam:
                result = max([*fam, result or 0.0])
        self._memo[model_id] = result
        return result

    def rating(self, model_id: str) -> float:
        r = self.lookup(model_id)
        return r if r is not None else DEFAULT_RATING


# --------------------------------------------------------------------------- final score


def score(rating: float, stat: dict[str, Any] | None, preference: str = "quality") -> float:
    """Higher is better.

    quality : arena rating, minus penalties for unreliable / currently rate-limited deployments
    speed   : favours low observed latency, rating as tie-breaker
    balanced: both
    """
    s = rating
    if stat:
        ok, fail = stat.get("ok", 0), stat.get("fail", 0)
        n = ok + fail
        if n:
            # Laplace-smoothed success rate; a model failing half the time loses ~100 Elo.
            rate = (ok + 1) / (n + 2)
            s -= (1 - rate) * 200
        last_rl = stat.get("last_rate_limit", 0)
        if last_rl and time.time() - last_rl < 600:
            s -= 150  # rate-limited in the last 10 minutes: try others first
        if stat.get("last_auth_error", 0) > stat.get("last_ok", 0):
            s -= 1000  # bad key / no access: effectively last
        lat = stat.get("latency")
        if lat and preference in ("speed", "balanced"):
            weight = 60 if preference == "speed" else 20
            s -= weight * lat  # seconds
    return s
