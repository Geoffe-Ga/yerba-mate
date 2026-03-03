"""Shared test fixtures for the yerba mate reduction bot."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add project root to sys.path so bare `import db` / `import commands` work.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import db  # noqa: E402
from planner import LARGE_MG, SMALL_MG, PlanDay  # noqa: E402

if TYPE_CHECKING:
    from datetime import date


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with tables initialised."""
    path = tmp_path / "test.db"
    db.init_db(path)
    return path


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
def cog() -> MagicMock:
    """Return a ``YerbaCog`` backed by a mock bot."""
    from commands import YerbaCog

    bot = MagicMock()
    return YerbaCog(bot)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_plan_day(
    d: date,
    *,
    small: int = 0,
    large: int = 0,
) -> PlanDay:
    """Create a ``PlanDay`` with auto-calculated ``total_mg``."""
    return PlanDay(
        date=d,
        small=small,
        large=large,
        total_mg=(SMALL_MG * small) + (LARGE_MG * large),
    )
