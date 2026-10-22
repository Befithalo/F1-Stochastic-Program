"""The one network door: a polite, caching JSON client for the real data sources (D-08, D-14).

Only this module imports `requests` and `requests_cache` (the import ban in `tests/guards` enforces
it), and only the Jolpica and OpenF1 adapters import this module. Everything else sees the
`JsonGetter` protocol, so tests hand in fakes and never touch the network.

Pacing
------
Both services are free and shared, so we stay well below their published limits:

* OpenF1 free tier: 3 requests per second and 30 per minute. One call every 2.1 s is at most
  28.6 calls per minute, which leaves a margin. (The OpenF1 adapter picks this value.)
* Jolpica: 4 requests per second burst and 500 per hour. We space calls 0.5 s apart and allow at
  most 450 real network calls in any rolling 3600 s window (10 percent margin).

Pacing applies to real network calls only. A response served from the on-disk cache is neither
delayed after the fact nor counted toward the hourly window, so re-running a load makes no repeat
calls and costs no quota.

Retries
-------
* HTTP 429 (throttled): wait the number of seconds in the `Retry-After` header when it is numeric
  (capped at one hour), otherwise 5, 15, 45, then 90 s. At most four waits; the fifth 429 raises
  `RateLimitedError` carrying the last wait so the loader can decide what to do.
* HTTP 5xx: wait 5 s, then 15 s, then give up with a `SourceError`.
* Network failures (no internet, timeout) become one-line `SourceError` messages that say what to do
  next. Nothing else is retried.

Caching
-------
Responses are cached in SQLite with the JSON serializer, never an object-pickling format: a cache
restored from somewhere else (for example a CI cache) could then execute code when loaded. Only HTTP
200 responses are cached (`allowable_codes=(200,)`), so a throttled or failed response is never
stored.
Historical data never expires; schedule responses (`freshness="short"`) expire after 12 hours so a
new race appears the day after it is run. TLS verification is never disabled.
"""

import math
import time
from collections import deque
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Final, Literal, Protocol

import requests
import requests_cache

from f1si.data.sources import RateLimitedError, SourceError

USER_AGENT: Final = "f1si/0.1.0 (+https://github.com/Befithalo/F1-Stochastic-Program)"
SHORT_EXPIRY: Final = timedelta(hours=12)
HOUR_S: Final = 3600.0
RATE_LIMIT_WAITS_S: Final = (5.0, 15.0, 45.0, 90.0)
SERVER_ERROR_WAITS_S: Final = (5.0, 15.0)
MAX_RETRY_AFTER_S: Final = 3600.0

Freshness = Literal["forever", "short"]


class HttpResponse(Protocol):
    """The part of a `requests` response the client uses."""

    @property
    def status_code(self) -> int:
        """HTTP status code."""
        ...

    @property
    def headers(self) -> Mapping[str, str]:
        """Response headers."""
        ...

    def json(self) -> object:
        """Parsed JSON body; raises `ValueError` when the body is not JSON."""
        ...


class HttpSession(Protocol):
    """The part of a `requests_cache.CachedSession` the client uses."""

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None,
        timeout: float,
        expire_after: object,
    ) -> HttpResponse:
        """GET `url`; a cached response has a truthy `from_cache` attribute."""
        ...


class JsonGetter(Protocol):
    """What the adapters depend on: fetch JSON by path, or None when the server says 404."""

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int] | None = None,
        *,
        freshness: Freshness = "forever",
    ) -> object:
        """Return the parsed JSON for `path` (starts with `/`), or None for HTTP 404."""
        ...


class RateLimitedClient:
    """Paced, retrying, caching JSON client for one service (see the module docstring)."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        min_interval_s: float,
        max_per_hour: int | None,
        cache_path: Path,
        echo: Callable[[str], None] = print,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        session: HttpSession | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError(f"base_url must start with https:// (got {base_url!r})")
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._min_interval_s = min_interval_s
        self._max_per_hour = max_per_hour
        self._echo = echo
        self._sleep = sleep
        self._clock = clock
        self._timeout_s = timeout_s
        self._calls: deque[float] = deque()
        self._last_call: float | None = None
        self._owned: requests_cache.CachedSession | None = None
        if session is None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._owned = requests_cache.CachedSession(
                cache_name=str(cache_path),
                backend="sqlite",
                serializer="json",
                allowable_codes=(200,),
                expire_after=requests_cache.NEVER_EXPIRE,
            )
            self._owned.headers["User-Agent"] = USER_AGENT
            session = self._owned
        assert session is not None
        self._session: HttpSession = session

    def close(self) -> None:
        """Close the cache database when this client created it."""
        if self._owned is not None:
            self._owned.close()  # type: ignore[no-untyped-call]

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int] | None = None,
        *,
        freshness: Freshness = "forever",
    ) -> object:
        """Fetch `base_url + path` as JSON with pacing, retries and caching.

        Returns None on HTTP 404. Raises `RateLimitedError` after repeated 429 responses and
        `SourceError` for server errors, network problems and non-JSON bodies.
        """
        if not path.startswith("/") or "://" in path:
            raise ValueError(f"path must start with '/' and contain no scheme (got {path!r})")
        url = self._base_url + path
        expire_after: object = (
            requests_cache.NEVER_EXPIRE if freshness == "forever" else SHORT_EXPIRY
        )
        rate_waits = 0
        server_waits = 0
        last_wait = 0.0
        while True:
            response = self._send(url, params, expire_after)
            status = response.status_code
            if status == 200:
                return self._parse(response, path)
            if status == 404:
                return None
            if status == 429:
                if rate_waits >= len(RATE_LIMIT_WAITS_S):
                    raise RateLimitedError(
                        f"Rate limited by {self._name} (HTTP 429) on {path}; "
                        "run the same command again later",
                        retry_after_s=last_wait,
                    )
                wait = self._retry_after(response)
                if wait is None:
                    wait = RATE_LIMIT_WAITS_S[rate_waits]
                rate_waits += 1
                last_wait = wait
                self._echo(
                    f"Rate limited by {self._name} (HTTP 429); waiting {wait:g} s "
                    f"(retry {rate_waits} of {len(RATE_LIMIT_WAITS_S)})"
                )
                self._sleep(wait)
                continue
            if 500 <= status < 600:
                if server_waits >= len(SERVER_ERROR_WAITS_S):
                    raise SourceError(
                        f"{self._name} is having problems (HTTP {status}); try again later"
                    )
                wait = SERVER_ERROR_WAITS_S[server_waits]
                server_waits += 1
                self._echo(f"{self._name} returned HTTP {status}; waiting {wait:g} s to retry")
                self._sleep(wait)
                continue
            raise SourceError(f"{self._name} answered HTTP {status} for {path}")

    def _send(
        self,
        url: str,
        params: Mapping[str, str | int] | None,
        expire_after: object,
    ) -> HttpResponse:
        self._pace()
        sent_at = self._clock()
        try:
            response = self._session.get(
                url, params=params, timeout=self._timeout_s, expire_after=expire_after
            )
        except requests.RequestException as exc:
            raise SourceError(
                f"Network problem talking to {self._name} ({type(exc).__name__}: {exc}). "
                "Check your internet connection, then run the same command again; "
                "finished races are kept."
            ) from exc
        from_cache = bool(getattr(response, "from_cache", False))
        if not from_cache:
            self._last_call = sent_at
            self._calls.append(sent_at)
        return response

    def _pace(self) -> None:
        now = self._clock()
        if self._last_call is not None:
            remaining = self._min_interval_s - (now - self._last_call)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        if self._max_per_hour is None:
            return
        while self._calls and now - self._calls[0] >= HOUR_S:
            self._calls.popleft()
        if len(self._calls) >= self._max_per_hour:
            wait = max(self._calls[0] + HOUR_S - now, 0.0)
            self._echo(
                f"Waiting {math.ceil(wait)} s for the {self._name} hourly limit "
                f"({self._max_per_hour} calls per hour)..."
            )
            self._sleep(wait)
            self._calls.popleft()

    @staticmethod
    def _retry_after(response: HttpResponse) -> float | None:
        for key, value in response.headers.items():
            if key.lower() == "retry-after":
                try:
                    seconds = float(value)
                except ValueError:
                    return None
                if math.isfinite(seconds) and seconds >= 0:
                    return min(seconds, MAX_RETRY_AFTER_S)
                return None
        return None

    def _parse(self, response: HttpResponse, path: str) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(
                f"Unexpected (non-JSON) response from {self._name} for {path}"
            ) from exc
