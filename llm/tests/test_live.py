"""Real network calls against keyless providers. Run: uv run pytest -m live"""

import pytest

from freellm import FreeLLM

pytestmark = pytest.mark.live


def test_keyless_discovery_and_completion():
    fl = FreeLLM(providers=["ovh", "llm7"], refresh=True)
    assert fl.ranked(), "no keyless models discovered"
    out = fl.complete("Reply with the word ok.", max_tokens=400)
    assert isinstance(out, str)
