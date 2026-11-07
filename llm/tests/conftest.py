import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from freellm import config

# Point FREELLM_HOME at a throwaway folder for the whole session, never back at llm/.
# LiteLLM logs some callbacks on background threads that can fire after a test ends;
# those late writes must not reach the real llm/.cache/stats.json.
_SESSION_HOME = tempfile.mkdtemp(prefix="freellm-tests-")
os.environ["FREELLM_HOME"] = _SESSION_HOME


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Every test gets an empty FREELLM_HOME (no real keys, cache or stats)."""
    monkeypatch.setenv("FREELLM_HOME", str(tmp_path))
    for k in list(os.environ):
        if k.endswith(("_API_KEY", "_TOKEN")) or "_API_KEY_" in k:
            monkeypatch.delenv(k, raising=False)
    config.reload_env()
    yield tmp_path
    # monkeypatch restores FREELLM_HOME to the session temp dir, not to llm/
    config.reload_env()
