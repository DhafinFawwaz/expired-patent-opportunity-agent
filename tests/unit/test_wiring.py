from pathlib import Path

import httpx

from patentic.adapters.http import FetchResult, HttpSource
from patentic.config.settings import Settings
from patentic.graph.deps import Deps
from patentic.wiring import USER_AGENT, make_deps

URL: str = "https://www.uspto.gov/web/offices/com/sol/og/2026/week44/TOC.htm"


def test_simulated_gazette_outage_ignores_a_warm_cache(tmp_path: Path) -> None:
    cache: Path = tmp_path / "cache"
    warm: HttpSource = HttpSource(
        "og",
        cache / "http",
        None,
        1000.0,
        USER_AGENT,
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html></html>")),
    )
    assert warm.get(URL).status == 200
    settings: Settings = Settings(
        patentic_cache_dir=cache, patentic_outputs_dir=tmp_path / "out", _env_file=None
    )
    deps: Deps = make_deps(settings, demo=False, no_llm=True, offline=False, simulate_outage="og")
    result: FetchResult = deps.og._http.get(URL)
    assert result.status != 200
    assert not result.from_cache


def test_offline_run_keeps_ops_offline(tmp_path: Path) -> None:
    settings: Settings = Settings(
        epo_ops_key="k",
        epo_ops_secret="s",
        patentic_cache_dir=tmp_path / "cache",
        patentic_outputs_dir=tmp_path / "out",
        _env_file=None,
    )
    deps: Deps = make_deps(settings, demo=False, no_llm=True, offline=True, simulate_outage=None)
    assert deps.ops.offline
