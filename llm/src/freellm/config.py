"""Where freellm keeps keys, cache and stats, and how API keys are read.

Key lookup order (first wins for each variable):
  1. the process environment
  2. ``$FREELLM_HOME/.env`` (default: the ``llm/`` project folder, which is git-ignored)

A provider can have several keys. For ``key_env: GROQ_API_KEY`` all of these are picked up:
  GROQ_API_KEY=k1            GROQ_API_KEY_2=k2   GROQ_API_KEY_3=k3 ...
  GROQ_API_KEY=k1,k2,k3      (comma-separated also works)
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values

_PKG_DIR = Path(__file__).resolve().parent


def home() -> Path:
    """The freellm home folder: holds ``.env`` and ``.cache/``."""
    env = os.environ.get("FREELLM_HOME")
    if env:
        return Path(env).expanduser().resolve()
    # Editable / in-repo install: src/freellm -> llm/
    project = _PKG_DIR.parent.parent
    if (project / "pyproject.toml").exists():
        return project
    return Path.home() / ".config" / "freellm"


def env_file() -> Path:
    return home() / ".env"


def cache_dir() -> Path:
    d = home() / ".cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


@lru_cache(maxsize=1)
def _dotenv() -> dict[str, str]:
    f = env_file()
    if not f.exists():
        return {}
    return {k: v for k, v in dotenv_values(f).items() if v}


def reload_env() -> None:
    _dotenv.cache_clear()


def get_env(name: str) -> str | None:
    return os.environ.get(name) or _dotenv().get(name)


def _all_env() -> dict[str, str]:
    merged = dict(_dotenv())
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def get_keys(key_env: str) -> list[str]:
    """All keys for one provider, de-duplicated, in a stable order."""
    pattern = re.compile(rf"^{re.escape(key_env)}(?:_(\d+))?$")
    found: list[tuple[int, str]] = []
    for name, value in _all_env().items():
        m = pattern.match(name)
        if m:
            found.append((int(m.group(1) or 1), value))
    keys: list[str] = []
    for _, value in sorted(found):
        for part in value.split(","):
            part = part.strip()
            if part and part not in keys and not part.startswith("your-"):
                keys.append(part)
    return keys


def fill_placeholders(text: str) -> str | None:
    """Replace ``{ENV_VAR}`` placeholders; None if any is missing."""
    missing = False

    def sub(m: re.Match[str]) -> str:
        nonlocal missing
        v = get_env(m.group(1))
        if not v:
            missing = True
            return ""
        return v

    out = re.sub(r"\{([A-Z0-9_]+)\}", sub, text)
    return None if missing else out


def mask(key: str) -> str:
    return key[:4] + "…" + key[-4:] if len(key) > 12 else "…"
