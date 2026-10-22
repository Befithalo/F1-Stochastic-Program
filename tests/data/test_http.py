"""Offline tests for the rate-limited caching HTTP client (fake session, fake clock)."""

from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path

import pytest
import requests
import requests_cache

from f1si.data.sources import RateLimitedError, SourceError
from f1si.data.sources._http import RateLimitedClient

BASE = "https://example.test/api"


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: object = None,
        headers: Mapping[str, str] | None = None,
        *,
        from_cache: bool = False,
        bad_json: bool = False,
    ) -> None:
        self.status_code = status_code
        self.headers: Mapping[str, str] = headers or {}
        self.from_cache = from_cache
        self._payload = payload
        self._bad_json = bad_json

    def json(self) -> object:
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Returns queued responses (or raises queued exceptions) and records every call."""

    def __init__(self, *queue: FakeResponse | Exception) -> None:
        self.queue = list(queue)
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None,
        timeout: float,
        expire_after: object,
    ) -> FakeResponse:
        self.calls.append(
            {"url": url, "params": params, "timeout": timeout, "expire_after": expire_after}
        )
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class World:
    """A fake clock that advances when the injected sleep is called."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []
        self.messages: list[str] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def echo(self, message: str) -> None:
        self.messages.append(message)


def make(
    world: World,
    session: FakeSession,
    *,
    min_interval_s: float = 0.0,
    max_per_hour: int | None = None,
    tmp_path: Path,
) -> RateLimitedClient:
    return RateLimitedClient(
        name="Testservice",
        base_url=BASE,
        min_interval_s=min_interval_s,
        max_per_hour=max_per_hour,
        cache_path=tmp_path / "cache.sqlite",
        echo=world.echo,
        sleep=world.sleep,
        clock=world.clock,
        session=session,
    )


def test_consecutive_calls_sleep_the_remaining_interval(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(FakeResponse(payload=1), FakeResponse(payload=2))
    client = make(world, session, min_interval_s=2.1, tmp_path=tmp_path)
    client.get_json("/a")
    world.now += 0.5  # time spent elsewhere between the two calls
    client.get_json("/b")
    assert world.sleeps == [pytest.approx(1.6)]


def test_first_call_is_not_delayed(tmp_path: Path) -> None:
    world = World()
    client = make(
        world, FakeSession(FakeResponse(payload=1)), min_interval_s=2.1, tmp_path=tmp_path
    )
    client.get_json("/a")
    assert world.sleeps == []


def test_cached_responses_are_not_counted_or_paced_after(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(
        FakeResponse(payload=1),
        FakeResponse(payload=2, from_cache=True),
        FakeResponse(payload=3),
    )
    client = make(world, session, min_interval_s=2.1, max_per_hour=2, tmp_path=tmp_path)
    client.get_json("/a")
    world.now += 5.0
    client.get_json("/cached")
    # Spacing is measured from the last real network call, not from the cache hit.
    client.get_json("/c")
    assert world.sleeps == []
    assert not any("hourly" in m for m in world.messages)


def test_429_with_retry_after_waits_then_succeeds(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(
        FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(payload={"ok": 1})
    )
    client = make(world, session, tmp_path=tmp_path)
    assert client.get_json("/x") == {"ok": 1}
    assert world.sleeps == [7.0]
    assert any("429" in m and "retry 1 of 4" in m for m in world.messages)


def test_retry_after_header_is_case_insensitive_and_capped(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(
        FakeResponse(429, headers={"retry-after": "999999"}), FakeResponse(payload=1)
    )
    client = make(world, session, tmp_path=tmp_path)
    client.get_json("/x")
    assert world.sleeps == [3600.0]


def test_429_without_retry_after_uses_backoff_then_raises(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(*[FakeResponse(429) for _ in range(5)])
    client = make(world, session, tmp_path=tmp_path)
    with pytest.raises(RateLimitedError) as info:
        client.get_json("/x")
    assert world.sleeps == [5.0, 15.0, 45.0, 90.0]
    assert info.value.retry_after_s == 90.0
    assert len(session.calls) == 5


def test_non_numeric_retry_after_falls_back_to_backoff(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(
        FakeResponse(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        FakeResponse(payload=1),
    )
    client = make(world, session, tmp_path=tmp_path)
    client.get_json("/x")
    assert world.sleeps == [5.0]


def test_503_then_200_backs_off_once(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(FakeResponse(503), FakeResponse(payload=[1]))
    client = make(world, session, tmp_path=tmp_path)
    assert client.get_json("/x") == [1]
    assert world.sleeps == [5.0]


def test_three_503s_raise_source_error(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(FakeResponse(503), FakeResponse(503), FakeResponse(503))
    client = make(world, session, tmp_path=tmp_path)
    with pytest.raises(SourceError, match="having problems"):
        client.get_json("/x")
    assert world.sleeps == [5.0, 15.0]


@pytest.mark.parametrize("exc", [requests.ConnectionError("down"), requests.Timeout("slow")])
def test_network_errors_become_one_line_messages(exc: Exception, tmp_path: Path) -> None:
    client = make(World(), FakeSession(exc), tmp_path=tmp_path)
    with pytest.raises(SourceError) as info:
        client.get_json("/x")
    assert "internet connection" in str(info.value)
    assert "\n" not in str(info.value)


def test_non_json_body_raises_source_error(tmp_path: Path) -> None:
    client = make(World(), FakeSession(FakeResponse(bad_json=True)), tmp_path=tmp_path)
    with pytest.raises(SourceError, match="Unexpected"):
        client.get_json("/x")


def test_404_returns_none(tmp_path: Path) -> None:
    client = make(World(), FakeSession(FakeResponse(404)), tmp_path=tmp_path)
    assert client.get_json("/x") is None


def test_other_4xx_raises_with_code_and_path(tmp_path: Path) -> None:
    client = make(World(), FakeSession(FakeResponse(403)), tmp_path=tmp_path)
    with pytest.raises(SourceError, match=r"403.*/x"):
        client.get_json("/x")


def test_hourly_window_waits_for_the_oldest_call(tmp_path: Path) -> None:
    world = World()
    session = FakeSession(*[FakeResponse(payload=i) for i in range(4)])
    client = make(world, session, max_per_hour=2, tmp_path=tmp_path)
    client.get_json("/1")  # at t=1000
    world.now += 10
    client.get_json("/2")  # at t=1010
    world.now += 10  # t=1020, oldest call is 20 s old
    client.get_json("/3")
    assert any("hourly" in m and "2 calls per hour" in m for m in world.messages)
    assert world.sleeps == [pytest.approx(3600 - 20)]
    # The oldest call has left the window; call 4 only has to wait for the one from t=1010.
    client.get_json("/4")
    assert world.sleeps[1] == pytest.approx(10.0)


@pytest.mark.parametrize("path", ["https://example.com/x", "x", "/a://b"])
def test_bad_paths_are_rejected(path: str, tmp_path: Path) -> None:
    client = make(World(), FakeSession(), tmp_path=tmp_path)
    with pytest.raises(ValueError, match="path must start"):
        client.get_json(path)


def test_base_url_must_be_https(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="https"):
        RateLimitedClient(
            name="X",
            base_url="http://example.test",
            min_interval_s=0,
            max_per_hour=None,
            cache_path=tmp_path / "c.sqlite",
            session=FakeSession(),
        )


def test_freshness_sets_expire_after(tmp_path: Path) -> None:
    session = FakeSession(FakeResponse(payload=1), FakeResponse(payload=1))
    client = make(World(), session, tmp_path=tmp_path)
    client.get_json("/a", freshness="short")
    client.get_json("/b")
    assert session.calls[0]["expire_after"] == timedelta(hours=12)
    assert session.calls[1]["expire_after"] == requests_cache.NEVER_EXPIRE


def test_url_params_and_timeout_are_passed(tmp_path: Path) -> None:
    session = FakeSession(FakeResponse(payload=1))
    client = make(World(), session, tmp_path=tmp_path)
    client.get_json("/a", {"limit": 100})
    assert session.calls[0]["url"] == BASE + "/a"
    assert session.calls[0]["params"] == {"limit": 100}
    assert session.calls[0]["timeout"] == 30.0


def test_default_session_is_a_json_cache_at_the_given_path(tmp_path: Path) -> None:
    cache_path = tmp_path / "nested" / "svc.sqlite"
    client = RateLimitedClient(
        name="X",
        base_url=BASE,
        min_interval_s=0,
        max_per_hour=None,
        cache_path=cache_path,
    )
    try:
        session = client._owned
        assert isinstance(session, requests_cache.CachedSession)
        assert Path(session.cache.db_path) == cache_path
        assert "f1si" in session.headers["User-Agent"]
        assert session.cache.responses.serializer is not None
        assert tuple(session.settings.allowable_codes) == (200,)
        assert session.verify is True
    finally:
        client.close()
