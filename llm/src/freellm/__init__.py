"""freellm — route LangChain / LiteLLM calls to the best free LLM you have access to.

Quick use::

    from freellm import get_chat_model
    llm = get_chat_model()                 # LangChain BaseChatModel, best free model first
    llm.invoke("Hello").content

    from freellm import complete
    complete("Summarise this: ...")        # str -> str

Keys live in ``llm/.env`` (git-ignored). Run ``freellm keys`` to see which providers are set up
and where to get free keys.
"""

from __future__ import annotations

from typing import Any

from .catalog import ModelInfo, Provider, discover, load_providers
from .router import GROUPS, FreeLLM, RankedModel

__all__ = [
    "FreeLLM",
    "RankedModel",
    "Provider",
    "ModelInfo",
    "GROUPS",
    "get_chat_model",
    "get_router",
    "complete",
    "ranked_models",
    "load_providers",
    "discover",
]

_default: FreeLLM | None = None


def get_router(**kwargs: Any) -> FreeLLM:
    """The shared FreeLLM instance (built once per process). Pass kwargs to rebuild with options."""
    global _default
    if _default is None or kwargs:
        _default = FreeLLM(**kwargs)
    return _default


def get_chat_model(model: str | None = None, **kwargs: Any):
    """LangChain chat model over the best free models.

    model: "free" (default) | "free-tools" | "free-vision" | "free-fast" | a model name.
    kwargs: passed to the LangChain model (temperature, max_tokens, streaming, ...).
    """
    return get_router().chat_model(model, **kwargs)


def complete(prompt: str, model: str | None = None, **kwargs: Any) -> str:
    return get_router().complete(prompt, model=model, **kwargs)


def ranked_models(**filters: Any) -> list[RankedModel]:
    return get_router().ranked(**filters)
