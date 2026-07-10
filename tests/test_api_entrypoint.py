"""Tests for the standalone API entrypoint (issue #17).

Covers env-driven config loading (fail-fast, every missing var named),
real server boot on an ephemeral port, graceful shutdown via stop event
and via SIGTERM, and the ``main()`` wrapper.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import aiohttp
import pytest

import api

if TYPE_CHECKING:
    from collections.abc import Callable

VALID_ENV = {
    "RUBOTPAUL_SHARED_SECRET": "test-secret",
    "DATABASE_URL": "postgresql://localhost:5432/yerba_test",
}


def _free_port() -> int:
    """Reserve an ephemeral localhost port and return its number."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_reads_env() -> None:
    """All values come from the provided environment mapping."""
    config = api.load_config({**VALID_ENV, "YERBA_API_PORT": "9000"})
    assert config.database_url == VALID_ENV["DATABASE_URL"]
    assert config.port == 9000


def test_load_config_default_port() -> None:
    """YERBA_API_PORT defaults to 8001 when unset."""
    config = api.load_config(VALID_ENV)
    assert config.port == 8001


def test_load_config_missing_vars_names_all() -> None:
    """A single error names every missing required variable."""
    with pytest.raises(api.ApiConfigError) as excinfo:
        api.load_config({})
    message = str(excinfo.value)
    assert "RUBOTPAUL_SHARED_SECRET" in message
    assert "DATABASE_URL" in message


def test_load_config_empty_value_counts_as_missing() -> None:
    """Empty-string env values are treated as missing."""
    with pytest.raises(api.ApiConfigError) as excinfo:
        api.load_config({**VALID_ENV, "DATABASE_URL": ""})
    assert "DATABASE_URL" in str(excinfo.value)


def test_load_config_non_integer_port() -> None:
    """A non-integer port fails with a clear message."""
    with pytest.raises(api.ApiConfigError) as excinfo:
        api.load_config({**VALID_ENV, "YERBA_API_PORT": "not-a-port"})
    assert "YERBA_API_PORT" in str(excinfo.value)


@pytest.mark.parametrize("bad_port", ["0", "65536", "-1"])
def test_load_config_out_of_range_port(bad_port: str) -> None:
    """Ports outside 1-65535 are rejected."""
    with pytest.raises(api.ApiConfigError) as excinfo:
        api.load_config({**VALID_ENV, "YERBA_API_PORT": bad_port})
    assert "YERBA_API_PORT" in str(excinfo.value)


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    """Stub out db.init_db / db.close_db so serve() needs no Postgres."""
    init = MagicMock()
    close = MagicMock()
    monkeypatch.setattr(api.db, "init_db", init)
    monkeypatch.setattr(api.db, "close_db", close)
    return init, close


async def _wait_for_healthz(port: int) -> None:
    """Poll /healthz until the server answers or time runs out."""
    async with aiohttp.ClientSession() as session:
        for _ in range(100):
            try:
                async with session.get(f"http://127.0.0.1:{port}/healthz") as response:
                    assert await response.json() == {"ok": True}
                    return
            except aiohttp.ClientConnectorError:
                await asyncio.sleep(0.05)
    pytest.fail("server never answered /healthz")


async def _assert_connection_refused(port: int) -> None:
    """Assert nothing is listening on the port anymore."""
    async with aiohttp.ClientSession() as session:
        with pytest.raises(aiohttp.ClientConnectorError):
            await session.get(f"http://127.0.0.1:{port}/healthz")


async def test_serve_boots_healthz_and_stops_cleanly(
    fake_db: tuple[MagicMock, MagicMock],
) -> None:
    """serve() initialises the DB, answers /healthz, and cleans up on stop."""
    init, close = fake_db
    port = _free_port()
    config = api.ApiConfig(database_url=VALID_ENV["DATABASE_URL"], port=port)
    stop_event = asyncio.Event()
    task = asyncio.create_task(api.serve(config, stop_event=stop_event))

    await _wait_for_healthz(port)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    init.assert_called_once_with(VALID_ENV["DATABASE_URL"])
    close.assert_called_once_with()
    await _assert_connection_refused(port)


async def test_serve_sigterm_graceful_shutdown(
    fake_db: tuple[MagicMock, MagicMock],
) -> None:
    """A real SIGTERM to the process shuts the server down cleanly."""
    _, close = fake_db
    port = _free_port()
    config = api.ApiConfig(database_url=VALID_ENV["DATABASE_URL"], port=port)
    task = asyncio.create_task(api.serve(config))

    await _wait_for_healthz(port)
    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(task, timeout=5)

    close.assert_called_once_with()
    await _assert_connection_refused(port)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove entrypoint env vars and neutralise .env loading."""
    for name in (*api.REQUIRED_ENV_VARS, "YERBA_API_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api, "load_dotenv", MagicMock())


def test_main_exits_with_clear_error_on_missing_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() exits naming the missing variables instead of tracebacking."""
    _scrub_env(monkeypatch)
    with pytest.raises(SystemExit) as excinfo:
        api.main()
    message = str(excinfo.value)
    assert "RUBOTPAUL_SHARED_SECRET" in message
    assert "DATABASE_URL" in message


def test_main_runs_serve_with_loaded_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() loads config from the environment and hands it to serve()."""
    _scrub_env(monkeypatch)
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("YERBA_API_PORT", "9137")

    served: list[api.ApiConfig] = []

    async def fake_serve(config: api.ApiConfig) -> None:
        served.append(config)

    fake: Callable[[api.ApiConfig], object] = fake_serve
    monkeypatch.setattr(api, "serve", fake)
    api.main()

    assert served == [api.ApiConfig(database_url=VALID_ENV["DATABASE_URL"], port=9137)]
