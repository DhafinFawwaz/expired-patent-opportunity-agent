import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
from freellm import FreeLLM, config, stats
from freellm._anon import ANON_KEY, _strip
from freellm.catalog import ModelInfo, Provider, _parse_model
from freellm.ranking import Ratings, canonical, score
from freellm.router import Deployment
from langchain_core.tools import tool

ARENA = [
    {"model_name": "GLM-5.3-Flash", "rating": 1470},
    {"model_name": "gpt-oss-120b", "rating": 1365},
    {"model_name": "Llama 3.3 70B Instruct", "rating": 1274},
    {"model_name": "Mistral Small 3.2 (2506)", "rating": 1338},
]


# ---------------------------------------------------------------- keys


def test_multiple_keys_numbered_and_comma(
    monkeypatch: pytest.MonkeyPatch, isolated_home: Path
) -> None:
    (isolated_home / ".env").write_text("GROQ_API_KEY_2=file2\nGROQ_API_KEY_3=env1\n")
    monkeypatch.setenv("GROQ_API_KEY", "env1,env2")
    config.reload_env()
    assert config.get_keys("GROQ_API_KEY") == ["env1", "env2", "file2"]


def test_placeholder_keys_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "your-key-here")
    assert config.get_keys("GROQ_API_KEY") == []


def test_api_base_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    p = Provider(
        id="cf", name="cf", api_base="https://x/{CLOUDFLARE_ACCOUNT_ID}/v1", key_env="CF_T"
    )
    monkeypatch.setenv("CF_T", "k")
    usable_without_account: bool = p.usable
    assert not usable_without_account
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc")
    usable_with_account: bool = p.usable
    assert usable_with_account
    assert p.resolved_api_base == "https://x/abc/v1"


# ---------------------------------------------------------------- ranking


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("openai/gpt-oss-120b", 1365),
        ("Meta-Llama-3_3-70B-Instruct", 1274),
        ("llama-3.3-70b-versatile", 1274),
        ("@cf/meta/llama-3.3-70b-instruct-fp8-fast", 1274),
        ("zai-glm-5.3-flash", 1470),
        ("Mistral-Small-3.2-24B-Instruct-2506", 1338),
        ("totally-unknown-model", None),
    ],
)
def test_arena_matching(model_id: str, expected: int | None) -> None:
    assert Ratings(ARENA).lookup(model_id) == expected


def test_same_model_same_canonical() -> None:
    assert (
        canonical("openai/gpt-oss-120b") == canonical("gpt-oss-120b") == canonical("gpt-oss:120b")
    )
    assert canonical("gpt-oss-20b") != canonical("gpt-oss-120b")


def test_score_penalties() -> None:
    import time

    assert score(1400, {"ok": 10, "fail": 0}) > score(1400, {"ok": 5, "fail": 5})
    assert score(1400, {"ok": 1, "fail": 1, "last_rate_limit": time.time()}) < 1300
    assert score(1400, {"ok": 0, "fail": 1, "last_auth_error": 2, "last_ok": 1}) < 500


# ---------------------------------------------------------------- discovery filters


def test_free_filters() -> None:
    orp = Provider(id="openrouter", name="", api_base="", key_env="X", free_filter="openrouter")
    free_model: ModelInfo | None = _parse_model(
        orp,
        {
            "id": "a/b:free",
            "pricing": {"prompt": "0", "completion": "0"},
            "supported_parameters": ["tools"],
        },
    )
    assert free_model is not None
    assert free_model.tools
    assert _parse_model(orp, {"id": "a/b", "pricing": {"prompt": "0.1", "completion": "0"}}) is None
    llm7 = Provider(
        id="llm7", name="", api_base="", key_env="X", free_filter="field:usage_based_only=false"
    )
    assert _parse_model(llm7, {"id": "m", "usage_based_only": False, "model_type": "chat"})
    assert _parse_model(llm7, {"id": "m", "usage_based_only": True}) is None
    zen = Provider(id="zen", name="", api_base="", key_env="X", free_filter="suffix:-free")
    assert _parse_model(zen, {"id": "deepseek-v4-flash-free"})
    assert not _parse_model(zen, {"id": "gpt-6"})
    allp = Provider(id="ovh", name="", api_base="", key_env="X")
    for non_chat in (
        "whisper-large-v3",
        "bge-m3",
        "Qwen3-Embedding-8B",
        "nvr-tts-en-us",
        "Qwen3Guard-Gen-8B",
    ):
        assert _parse_model(allp, {"id": non_chat}) is None, non_chat


# ---------------------------------------------------------------- routing (mocked, offline)

GOOD, RATE_LIMITED = "mocked answer", "litellm.RateLimitError"


def make(mocks: dict[str, str], keys: dict[str, list[str]] | None = None, **kw: Any) -> FreeLLM:
    """FreeLLM over fake providers. mocks: {"prov/model": mock_response}."""
    keys = keys or {}
    catalog: dict[Provider, list[ModelInfo]] = {}
    provs: dict[str, Provider] = {}
    for name in mocks:
        pid, mid = name.split("/", 1)
        if pid not in provs:
            provs[pid] = Provider(
                id=pid,
                name=pid,
                api_base=f"https://{pid}.invalid/v1",
                key_env=f"{pid.upper()}_API_KEY",
                keyless=pid not in keys,
            )
            catalog[provs[pid]] = []
        catalog[provs[pid]].append(ModelInfo(provider=pid, model_id=mid, tools=True))
    for pid, ks in keys.items():
        import os

        os.environ[f"{pid.upper()}_API_KEY"] = ",".join(ks)
    config.reload_env()
    fl = FreeLLM(catalog=catalog, arena_rows=ARENA, **kw)
    orig = fl._litellm_params

    def patched(d: Deployment, order: int | None) -> dict[str, Any]:
        p = orig(d, order)
        p["mock_response"] = mocks[f"{d.provider.id}/{d.model.model_id}"]
        return p

    fl._litellm_params = patched  # type: ignore[method-assign]
    return fl


def test_ranking_order_and_grouping() -> None:
    fl = make(
        {
            "a/gpt-oss-120b": GOOD,
            "b/gpt-oss-120b": GOOD,
            "a/GLM-5.3-Flash": GOOD,
            "a/mystery-7b": GOOD,
        }
    )
    names = [r.canonical for r in fl.ranked()]
    assert names == ["glm-5.3-flash", "gpt-oss-120b", "mystery-7b"]
    gpt = fl.ranked()[1]
    assert gpt.providers == ["a", "b"]  # same model from two providers merged


def test_multiple_keys_share_an_order_level() -> None:
    fl = make({"a/gpt-oss-120b": GOOD, "b/gpt-oss-120b": GOOD}, keys={"a": ["k1", "k2"]})
    free = [e for e in fl.model_list() if e["model_name"] == "free"]
    assert len(free) == 3  # a/k1, a/k2, b/anonymous
    assert {e["litellm_params"]["order"] for e in free} == {1}
    assert {e["litellm_params"]["api_key"] for e in free} == {"k1", "k2", ANON_KEY}


def test_falls_back_when_best_model_rate_limited() -> None:
    fl = make({"a/GLM-5.3-Flash": RATE_LIMITED, "b/gpt-oss-120b": GOOD})
    resp = fl.completion([{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == GOOD
    served: str | None = FreeLLM.served_by(resp)
    assert served is not None
    assert served.startswith("b:gpt-oss-120b")
    st = stats.load()
    glm = next(v for k, v in st.items() if k.startswith("a:GLM"))
    assert glm["fail"] >= 1
    assert glm.get("last_rate_limit")


def test_stats_demote_rate_limited_model_on_next_build() -> None:
    make({"a/GLM-5.3-Flash": RATE_LIMITED, "b/gpt-oss-120b": GOOD}).completion(
        [{"role": "user", "content": "hi"}]
    )
    fl2 = make({"a/GLM-5.3-Flash": GOOD, "b/gpt-oss-120b": GOOD})
    assert fl2.ranked()[0].canonical == "gpt-oss-120b"


def test_async_fallback() -> None:
    fl = make({"a/GLM-5.3-Flash": RATE_LIMITED, "b/gpt-oss-120b": GOOD})
    resp = asyncio.run(fl.acompletion([{"role": "user", "content": "hi"}]))
    assert resp.choices[0].message.content == GOOD


def test_named_model_and_resolve() -> None:
    fl = make({"a/gpt-oss-120b": GOOD, "b/GLM-5.3-Flash": GOOD})
    assert fl.resolve("openai/gpt-oss-120b") == "gpt-oss-120b"
    assert fl.resolve("b/GLM-5.3-Flash") == "b/GLM-5.3-Flash"
    with pytest.raises(ValueError):
        fl.resolve("nope-9000")


def test_exclude_models() -> None:
    fl = make({"a/gpt-oss-120b": GOOD, "a/GLM-5.3-Flash": GOOD}, exclude_models=["GLM-5.3-Flash"])
    assert [r.canonical for r in fl.ranked()] == ["gpt-oss-120b"]


def test_langchain_chat_model_invoke_and_tools() -> None:
    fl = make({"a/GLM-5.3-Flash": RATE_LIMITED, "b/gpt-oss-120b": GOOD})
    llm = fl.chat_model(temperature=0)
    assert llm.invoke("hi").content == GOOD

    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    assert fl.chat_model("free-tools").bind_tools([add]).invoke("add 1 2").content == GOOD


def test_no_models_gives_helpful_error() -> None:
    fl = FreeLLM(catalog={}, arena_rows=[])
    with pytest.raises(RuntimeError, match="freellm keys"):
        fl.router


# ---------------------------------------------------------------- anonymous auth header


def test_anonymous_header_stripped_real_keys_kept() -> None:
    anon = httpx.Request("POST", "https://x", headers={"Authorization": f"Bearer {ANON_KEY}"})
    _strip(anon)
    assert "authorization" not in anon.headers
    real = httpx.Request("POST", "https://x", headers={"Authorization": "Bearer sk-real"})
    _strip(real)
    assert real.headers["authorization"] == "Bearer sk-real"


@pytest.mark.parametrize(
    "msg", ["Error code: 402", "Add usage credits or subscribe", "A payment method is required"]
)
def test_payment_errors_classified(msg: str) -> None:
    assert stats.classify(msg) == "payment"


def test_available_is_deterministic_and_only_working() -> None:
    fl = make(
        {"a/GLM-5.3-Flash": RATE_LIMITED, "b/gpt-oss-120b": GOOD, "b/Llama-3.3-70B-Instruct": GOOD}
    )
    for name in ("a/GLM-5.3-Flash", "b/gpt-oss-120b", "b/Llama-3.3-70B-Instruct"):
        try:
            fl.router.completion(
                model=name, messages=[{"role": "user", "content": "hi"}], num_retries=0
            )
        except Exception:
            pass
    import time

    for _ in range(50):  # LiteLLM logs sync successes on a background thread
        if sum(1 for v in stats.load().values() if v.get("last_ok")) >= 2:
            break
        time.sleep(0.05)
    fl2 = make({"a/GLM-5.3-Flash": GOOD, "b/gpt-oss-120b": GOOD, "b/Llama-3.3-70B-Instruct": GOOD})
    names = [r.canonical for r, _ in fl2.available()]
    assert names == ["gpt-oss-120b", "llama-3.3-70b-instruct"]  # GLM failed last time, rating order
    assert names == [r.canonical for r, _ in fl2.available()]


def test_daily_free_limit_is_rate_limit_not_payment() -> None:
    assert (
        stats.classify(
            "litellm.RateLimitError: RateLimitError: OpenAIException - Free usage limit reached. subscribe"
        )
        == "rate_limit"
    )
