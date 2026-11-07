from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from patentic.adapters.http import FetchResult, HttpSource, outage_transport


class Clock:
    def __init__(self) -> None:
        self.now: datetime = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def source(
    tmp_path: Path,
    handler: httpx.MockTransport,
    ttl: timedelta | None = None,
    rate: float = 100.0,
) -> tuple[HttpSource, Clock, Sleeps]:
    clock: Clock = Clock()
    sleeps: Sleeps = Sleeps()
    http: HttpSource = HttpSource(
        name="og",
        cache_dir=tmp_path,
        ttl=ttl,
        rate_per_second=rate,
        user_agent="patentic-test",
        transport=handler,
        clock=clock,
        sleep=sleeps,
    )
    return http, clock, sleeps


def counting(status: int, body: str = "ok") -> tuple[httpx.MockTransport, list[int]]:
    calls: list[int] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status, text=body)

    return httpx.MockTransport(handle), calls


def test_get_caches_2xx_and_marks_from_cache(tmp_path: Path) -> None:
    transport, calls = counting(200, "<pre>rows</pre>")
    http, _, _ = source(tmp_path, transport)
    first: FetchResult = http.get("https://example.test/a")
    second: FetchResult = http.get("https://example.test/a")
    assert (first.status, first.from_cache, second.from_cache) == (200, False, True)
    assert second.text == "<pre>rows</pre>"
    assert len(calls) == 1


def test_get_does_not_cache_404(tmp_path: Path) -> None:
    transport, calls = counting(404)
    http, _, _ = source(tmp_path, transport)
    assert http.get("https://example.test/missing").status == 404
    assert http.get("https://example.test/missing").status == 404
    assert len(calls) == 2


def test_retries_then_returns_status_zero_on_transport_error(tmp_path: Path) -> None:
    calls: list[int] = []

    def boom(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        msg: str = "refused"
        raise httpx.ConnectError(msg, request=request)

    http, _, _ = source(tmp_path, httpx.MockTransport(boom))
    assert http.get("https://example.test/a").status == 0
    assert len(calls) == 4


def test_no_retry_on_403(tmp_path: Path) -> None:
    transport, calls = counting(403)
    http, _, _ = source(tmp_path, transport)
    assert http.get("https://example.test/a").status == 403
    assert len(calls) == 1


def test_outage_transport_yields_503_after_retries(tmp_path: Path) -> None:
    http, _, sleeps = source(tmp_path, outage_transport())
    result: FetchResult = http.get("https://example.test/a")
    assert result.status == 503
    assert not result.from_cache
    assert len([s for s in sleeps.calls if s > 0]) >= 3


def test_retry_after_header_is_honoured(tmp_path: Path) -> None:
    replies: list[httpx.Response] = [
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, text="ok"),
    ]
    http, _, sleeps = source(tmp_path, httpx.MockTransport(lambda r: replies.pop(0)))
    assert http.get("https://example.test/a").status == 200
    assert 7.0 in sleeps.calls


def test_rate_limiter_spaces_requests(tmp_path: Path) -> None:
    transport, _ = counting(200)
    http, _, sleeps = source(tmp_path, transport, rate=1.0)
    http.get("https://example.test/a")
    http.get("https://example.test/b")
    assert sleeps.calls == [1.0]


def test_ttl_expiry_refetches(tmp_path: Path) -> None:
    transport, calls = counting(200)
    http, clock, _ = source(tmp_path, transport, ttl=timedelta(hours=24))
    http.get("https://example.test/a")
    clock.now += timedelta(hours=25)
    assert not http.get("https://example.test/a").from_cache
    assert len(calls) == 2


def test_offline_source_never_calls_network(tmp_path: Path) -> None:
    transport, calls = counting(200)
    http: HttpSource = HttpSource(
        "og", tmp_path, None, 1.0, "t", transport=transport, offline=True, sleep=lambda _s: None
    )
    assert http.get("https://example.test/a").status == 0
    assert calls == []
