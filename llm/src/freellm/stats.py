"""Per-deployment health stats, recorded from LiteLLM callbacks and persisted to ``.cache/stats.json``.

A deployment is one (provider, model, key). Stats feed back into ranking on the next router build,
so a model that keeps failing or hitting rate limits sinks, and one that works rises again.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

from . import config

_LOCK = threading.Lock()
EWMA = 0.3  # weight of the newest latency sample


def stats_path() -> Path:
    return config.cache_dir() / "stats.json"


def load() -> dict[str, dict[str, Any]]:
    p = stats_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    p = stats_path()
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    tmp.replace(p)


def record(key: str, ok: bool, latency: float | None = None, error: BaseException | str | None = None) -> None:
    with _LOCK:
        data = load()
        s = data.setdefault(key, {"ok": 0, "fail": 0})
        now = time.time()
        if ok:
            s["ok"] += 1
            s["last_ok"] = now
            if latency is not None:
                prev = s.get("latency")
                s["latency"] = round(latency if prev is None else EWMA * latency + (1 - EWMA) * prev, 3)
        else:
            s["fail"] += 1
            s["last_fail"] = now
            kind = classify(error)
            s["last_error"] = f"{kind}: {str(error)[:200]}"
            if kind == "rate_limit":
                s["last_rate_limit"] = now
            elif kind in ("auth", "payment"):
                s["last_auth_error"] = now  # bad key or not free for this account: rank last until it works
        # Old evidence fades: halve counts once they get large so the score can recover.
        if s["ok"] + s["fail"] > 200:
            s["ok"] //= 2
            s["fail"] //= 2
        _save(data)


def reset() -> None:
    with _LOCK:
        p = stats_path()
        if p.exists():
            p.unlink()


def classify(error: BaseException | str | None) -> str:
    name = type(error).__name__ if isinstance(error, BaseException) else ""
    text = f"{name} {error}".lower()
    if "ratelimiterror" in text.replace(" ", "") or "usage limit" in text:
        return "rate_limit"  # includes daily free quotas ("Free usage limit reached"): temporary
    if any(x in text for x in ("402", "usage credits", "payment method", "subscribe", "insufficient credit", "billing")):
        return "payment"  # not actually free for this account
    if "ratelimit" in text or "429" in text or "rate limit" in text or "quota" in text:
        return "rate_limit"
    if "authentication" in text or "401" in text or "403" in text or "permission" in text or "api key" in text:
        return "auth"
    if "notfound" in text or "404" in text or "does not exist" in text or "not found" in text:
        return "not_found"
    if "timeout" in text:
        return "timeout"
    if "contextwindow" in text or "context length" in text:
        return "context"
    return "error"


def _key_from_kwargs(kwargs: dict[str, Any]) -> str | None:
    lp = kwargs.get("litellm_params") or {}
    for info in (lp.get("model_info"), kwargs.get("model_info"), (lp.get("metadata") or {}).get("model_info")):
        if isinstance(info, dict) and info.get("freellm_key"):
            return info["freellm_key"]
    return None


def _latency(start: Any, end: Any) -> float | None:
    try:
        return (end - start).total_seconds()
    except Exception:
        return None


class StatsCallback(CustomLogger):
    """Feeds every LiteLLM success/failure for freellm deployments into :func:`record`."""

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        if key := _key_from_kwargs(kwargs):
            record(key, True, _latency(start_time, end_time))

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        if key := _key_from_kwargs(kwargs):
            record(key, False, error=kwargs.get("exception") or response_obj)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self.log_success_event(kwargs, response_obj, start_time, end_time)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self.log_failure_event(kwargs, response_obj, start_time, end_time)
