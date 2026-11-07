"""Anonymous (keyless) providers.

OpenAI-compatible clients always send ``Authorization: Bearer <key>``, and some anonymous tiers
(e.g. OVHcloud) reject any bearer value. freellm sends a sentinel key and an httpx request hook
removes that header before the request leaves. Requests with real keys are untouched.
"""

from __future__ import annotations

import httpx
import litellm

ANON_KEY = "freellm-anonymous"
_SENTINEL = f"Bearer {ANON_KEY}"


def _strip(request: httpx.Request) -> None:
    if request.headers.get("authorization") == _SENTINEL:
        del request.headers["authorization"]


async def _astrip(request: httpx.Request) -> None:
    _strip(request)


def install() -> None:
    """Idempotently attach the hook to LiteLLM's shared httpx sessions (creating them if unset)."""
    if litellm.client_session is None:
        litellm.client_session = httpx.Client(timeout=httpx.Timeout(600.0, connect=10.0))
    if litellm.aclient_session is None:
        litellm.aclient_session = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))
    hooks = litellm.client_session.event_hooks.setdefault("request", [])
    if _strip not in hooks:
        hooks.append(_strip)
    ahooks = litellm.aclient_session.event_hooks.setdefault("request", [])
    if _astrip not in ahooks:
        ahooks.append(_astrip)
