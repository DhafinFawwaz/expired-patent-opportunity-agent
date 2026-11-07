import hashlib
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
from pydantic import BaseModel, ConfigDict
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

RETRY_STATUSES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS: Final[int] = 4
MAX_RETRY_AFTER: Final[float] = 60.0
TIMEOUT_SECONDS: Final[float] = 30.0


def utc_now() -> datetime:
    return datetime.now(UTC)


class FetchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    status: int
    text: str
    retrieved_at: datetime
    from_cache: bool = False
    content_sha256: str


class _RetryableStatusError(Exception):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response: httpx.Response = response
        header: str | None = response.headers.get("Retry-After")
        self.retry_after: float | None = float(header) if header and header.isdigit() else None


def outage_transport(status: int = 503) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: httpx.Response(status, text="simulated outage"))


class HttpSource:
    def __init__(
        self,
        name: str,
        cache_dir: Path,
        ttl: timedelta | None,
        rate_per_second: float,
        user_agent: str,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.name: str = name
        self._cache_dir: Path = cache_dir / name
        self._ttl: timedelta | None = ttl
        self._interval: float = 1.0 / rate_per_second
        self._clock: Callable[[], datetime] = clock
        self._sleep: Callable[[float], None] = sleep
        self._last_request: datetime | None = None
        self._backoff: wait_exponential_jitter = wait_exponential_jitter(multiplier=0.5, max=8)
        self._client: httpx.Client = httpx.Client(
            transport=transport,
            headers={"User-Agent": user_agent},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def get(self, url: str) -> FetchResult:
        cached: FetchResult | None = self._read_cache(url)
        if cached is not None:
            return cached
        retrying: Retrying = Retrying(
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=self._wait,
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
            sleep=self._sleep,
            reraise=True,
        )
        try:
            response: httpx.Response = retrying(self._attempt, url)
        except httpx.TransportError:
            return self._result(url, 0, "")
        except _RetryableStatusError as exc:
            return self._result(url, exc.response.status_code, exc.response.text)
        result: FetchResult = self._result(url, response.status_code, response.text)
        if response.is_success:
            self._write_cache(url, result)
        return result

    def _attempt(self, url: str) -> httpx.Response:
        self._throttle()
        response: httpx.Response = self._client.get(url)
        if response.status_code in RETRY_STATUSES:
            raise _RetryableStatusError(response)
        return response

    def _throttle(self) -> None:
        now: datetime = self._clock()
        if self._last_request is not None:
            elapsed: float = (now - self._last_request).total_seconds()
            if elapsed < self._interval:
                self._sleep(self._interval - elapsed)
        self._last_request = self._clock()

    def _wait(self, state: RetryCallState) -> float:
        exc: BaseException | None = state.outcome.exception() if state.outcome else None
        if isinstance(exc, _RetryableStatusError) and exc.retry_after is not None:
            return min(exc.retry_after, MAX_RETRY_AFTER)
        return self._backoff(state)

    def _result(self, url: str, status: int, text: str) -> FetchResult:
        return FetchResult(
            url=url,
            status=status,
            text=text,
            retrieved_at=self._clock(),
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )

    def _cache_path(self, url: str) -> Path:
        return self._cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"

    def _read_cache(self, url: str) -> FetchResult | None:
        path: Path = self._cache_path(url)
        if not path.exists():
            return None
        stored: FetchResult = FetchResult.model_validate_json(path.read_text())
        if self._ttl is not None and self._clock() - stored.retrieved_at > self._ttl:
            return None
        return stored.model_copy(update={"from_cache": True})

    def _write_cache(self, url: str, result: FetchResult) -> None:
        path: Path = self._cache_path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json())
