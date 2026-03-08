"""Shared test fixtures for the yerba mate reduction bot."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

# ---------------------------------------------------------------------------
# Stub discord if it is not installed in the test environment
# ---------------------------------------------------------------------------


def _passthrough(**_kwargs: Any) -> Any:
    """Decorator factory that mimics discord.py's Command wrapper.

    Sets ``fn.callback = fn`` so tests can use ``.callback()`` consistently
    regardless of whether real discord.py decorators are present.
    """

    def _decorator(fn: Any) -> Any:
        fn.callback = fn
        return fn

    return _decorator


class _StubGroup:
    """Minimal stub for ``app_commands.Group``.

    Acts as a descriptor that, when accessed on a *class*, returns itself
    so the ``plan_group.command(...)`` decorators work at import time.
    """

    def __init__(self, **_kwargs: Any) -> None:
        pass

    def command(self, **_kwargs: Any) -> Any:
        """Mimic ``@group.command(...)`` — delegates to ``_passthrough``."""
        return _passthrough(**_kwargs)


def _install_discord_stubs() -> None:
    """Insert lightweight discord stubs so ``import commands`` works."""
    discord = types.ModuleType("discord")
    discord.Embed = MagicMock  # type: ignore[attr-defined]
    discord.Color = MagicMock()  # type: ignore[attr-defined]
    discord.Interaction = MagicMock  # type: ignore[attr-defined]
    discord.Intents = MagicMock()  # type: ignore[attr-defined]
    discord.TextChannel = MagicMock  # type: ignore[attr-defined]

    app_commands = types.ModuleType("discord.app_commands")
    app_commands.command = _passthrough  # type: ignore[attr-defined]
    app_commands.describe = _passthrough  # type: ignore[attr-defined]
    app_commands.choices = _passthrough  # type: ignore[attr-defined]
    app_commands.Choice = MagicMock  # type: ignore[attr-defined]
    app_commands.Group = _StubGroup  # type: ignore[attr-defined]

    ext = types.ModuleType("discord.ext")
    ext_commands = types.ModuleType("discord.ext.commands")
    ext_commands.Cog = type("Cog", (), {})  # type: ignore[attr-defined]
    ext_commands.Bot = MagicMock  # type: ignore[attr-defined]
    ext.commands = ext_commands  # type: ignore[attr-defined]

    discord.app_commands = app_commands  # type: ignore[attr-defined]
    discord.ext = ext  # type: ignore[attr-defined]

    for name, mod in [
        ("discord", discord),
        ("discord.app_commands", app_commands),
        ("discord.ext", ext),
        ("discord.ext.commands", ext_commands),
    ]:
        sys.modules[name] = mod


if "discord" not in sys.modules:
    _install_discord_stubs()


# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from helpers import make_plan_day as make_plan_day  # noqa: E402

import db  # noqa: E402

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://localhost:5432/yerba_mate_test",
)

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db() -> Generator[None, None, None]:
    """Initialise the test database and truncate tables between tests."""
    db.init_db(_TEST_DATABASE_URL)
    with db._connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE plan_days, actuals")
        conn.commit()
    yield
    db.close_db()


# ---------------------------------------------------------------------------
# Discord mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_interaction() -> MagicMock:
    """Return a mock ``discord.Interaction`` with an ``AsyncMock`` response."""
    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.fixture()
def cog() -> Any:
    """Return a ``YerbaCog`` backed by a mock bot."""
    from commands import YerbaCog

    bot = MagicMock()
    return YerbaCog(bot)
