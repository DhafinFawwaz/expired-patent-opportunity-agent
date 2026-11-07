"""Providers (from providers.yaml) and live model discovery via each provider's ``/models``."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml

from . import config

log = logging.getLogger("freellm")

PROVIDERS_FILE = Path(__file__).with_name("providers.yaml")
DISCOVERY_TTL = 12 * 3600

# Models that are not chat/text-generation models.
NON_CHAT = re.compile(
    r"whisper|tts|embed|bge-|guard|rerank|stable-diffusion|sdxl|flux|dall-e|gpt-image|image-|-image|"
    r"imagen|veo|kling|lyria|speech|voice|transcri|moderation|audio|ocr|clip|nano-banana|chroma|"
    r"krea|safety|reward|parse|seg-|detect|-vl-embed|sora|orpheus|playai|lyria",
    re.IGNORECASE,
)


@dataclass(eq=False)  # hashable by identity: used as dict key
class Provider:
    id: str
    name: str
    api_base: str
    key_env: str
    signup_url: str = ""
    steps: list[str] = field(default_factory=list)
    limits: str = ""
    rpm: int = 10
    keyless: bool = False
    free_filter: str = "all"
    exclude: list[str] = field(default_factory=list)
    seed_models: list[str] = field(default_factory=list)
    extra_env: list[str] = field(default_factory=list)
    litellm_prefix: str = "openai"
    verified: str = ""

    @property
    def keys(self) -> list[str]:
        return config.get_keys(self.key_env)

    @property
    def resolved_api_base(self) -> str | None:
        return config.fill_placeholders(self.api_base)

    @property
    def usable(self) -> bool:
        """True if requests can be sent: a key exists (or none is needed) and the URL is complete."""
        return bool(self.keys or self.keyless) and self.resolved_api_base is not None

    @property
    def credentials(self) -> list[str | None]:
        """One entry per deployment to create. ``None`` = anonymous."""
        if self.keys:
            return list(self.keys)
        return [None] if self.keyless else []


_VISION_HINT = re.compile(
    r"(^|[-_/.])vl\b|vision|omni|gemma-?[34]\b|llama-4|pixtral|gemini", re.IGNORECASE
)


@dataclass
class ModelInfo:
    provider: str
    model_id: str
    name: str = ""
    context: int | None = None
    tools: bool | None = None
    vision: bool | None = None
    source: str = "seed"  # "live" (from /models) or "seed" (providers.yaml)

    def __post_init__(self) -> None:
        if self.vision is None and _VISION_HINT.search(self.model_id):
            self.vision = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def load_providers(path: Path | None = None) -> dict[str, Provider]:
    data = yaml.safe_load((path or PROVIDERS_FILE).read_text())
    extra = config.home() / "providers.local.yaml"  # optional user overrides / additions
    if extra.exists():
        local = yaml.safe_load(extra.read_text()) or {}
        for pid, spec in (local.get("providers") or {}).items():
            data["providers"].setdefault(pid, {}).update(spec)
    out: dict[str, Provider] = {}
    for pid, spec in data["providers"].items():
        if spec.get("disabled"):
            continue
        known = {k: v for k, v in spec.items() if k in Provider.__dataclass_fields__}
        out[pid] = Provider(id=pid, **known)
    return out


# --------------------------------------------------------------------------- discovery


def _cache_path(pid: str) -> Path:
    return config.cache_dir() / f"models_{pid}.json"


def _is_free(p: Provider, m: dict[str, Any]) -> bool:
    f = p.free_filter
    mid = str(m.get("id", ""))
    if f == "all":
        return True
    if f == "openrouter":
        pr = m.get("pricing") or {}
        return str(pr.get("prompt")) == "0" and str(pr.get("completion")) == "0"
    if f.startswith("suffix:"):
        return mid.endswith(f[len("suffix:") :])
    if f.startswith("field:"):
        k, _, v = f[len("field:") :].partition("=")
        return str(m.get(k)).lower() == v.lower()
    return False


def _parse_model(p: Provider, m: dict[str, Any]) -> ModelInfo | None:
    mid = str(m.get("id", "")).removeprefix("models/")
    if not mid or not _is_free(p, m):
        return None
    arch = m.get("architecture") or {}
    outs = arch.get("output_modalities") or (m.get("modalities") or {}).get("output")
    if outs and "text" not in outs:
        return None
    if m.get("model_type") and m["model_type"] != "chat":
        return None
    if NON_CHAT.search(mid) or any(re.search(x, mid, re.IGNORECASE) for x in p.exclude):
        return None
    caps = m.get("capabilities") or {}
    params = m.get("supported_parameters")
    tools = (
        caps.get("tools")
        if "tools" in caps
        else (("tools" in params) if params is not None else None)
    )
    ins = arch.get("input_modalities") or (m.get("modalities") or {}).get("input")
    vision = caps.get("vision") if "vision" in caps else (("image" in ins) if ins else None)
    ctx = (
        m.get("context_length")
        or (m.get("context_window") or {}).get("tokens")
        or m.get("context_window")
    )
    return ModelInfo(
        provider=p.id,
        model_id=mid,
        name=str(m.get("name") or mid),
        context=ctx if isinstance(ctx, int) else None,
        tools=tools,
        vision=vision,
        source="live",
    )


def _fetch(p: Provider) -> list[dict[str, Any]]:
    base = p.resolved_api_base
    if base is None:
        raise RuntimeError(f"missing {p.extra_env}")
    headers = {"Authorization": f"Bearer {p.keys[0]}"} if p.keys else {}
    r = httpx.get(base.rstrip("/") + "/models", headers=headers, timeout=20, follow_redirects=True)
    r.raise_for_status()
    body = r.json()
    rows = body.get("data", body.get("models", body)) if isinstance(body, dict) else body
    return rows if isinstance(rows, list) else []


def discover(p: Provider, refresh: bool = False) -> list[ModelInfo]:
    """Free chat models of one provider. Live list (cached 12h), falling back to seed_models."""
    seeds = [ModelInfo(provider=p.id, model_id=s, name=s) for s in p.seed_models]
    can_list = p.free_filter != "seed" and (p.usable or p.id == "openrouter")
    if not can_list:
        return seeds
    cp = _cache_path(p.id)
    if not refresh and cp.exists():
        cached = json.loads(cp.read_text())
        if time.time() - cached.get("ts", 0) < DISCOVERY_TTL and cached.get("models"):
            return [ModelInfo(**m) for m in cached["models"]]
    try:
        models = [mi for mi in (_parse_model(p, m) for m in _fetch(p)) if mi]
    except Exception as e:  # network, auth, odd payload: keep working with seeds / stale cache
        log.warning("freellm: model discovery failed for %s: %s", p.id, e)
        if cp.exists():
            return [ModelInfo(**m) for m in json.loads(cp.read_text()).get("models", [])] or seeds
        return seeds
    if not models:
        return seeds
    cp.write_text(
        json.dumps({"ts": time.time(), "models": [m.to_dict() for m in models]}, indent=1)
    )
    return models
