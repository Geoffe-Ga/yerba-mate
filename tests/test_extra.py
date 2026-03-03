"""Tests for the /extra command baseline behaviour (PR #6)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is importable (conftest.py handles discord stubs)
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from commands import YerbaCog  # noqa: E402
from planner import PlanDay  # noqa: E402

FIXED_TODAY = date(2025, 6, 15)


def _make_cog() -> YerbaCog:
    return YerbaCog(MagicMock())


def _interaction() -> MagicMock:
    ix = MagicMock()
    ix.response = AsyncMock()
    ix.response.send_message = AsyncMock()
    return ix


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_small_no_prior_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
) -> None:
    """With no logged actual, /extra small starts from 0 and adds 1 small."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_actual.side_effect = [
        None,
        PlanDay(date=FIXED_TODAY, small=1, large=0, total_mg=115),
    ]
    mock_db.get_plan_day.return_value = None
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    cog = _make_cog()
    ix = _interaction()
    await cog.extra(ix, "small")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=1, large=0)
    ix.response.send_message.assert_awaited_once()


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_large_no_prior_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
) -> None:
    """With no logged actual, /extra large starts from 0 and adds 1 large."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_actual.side_effect = [
        None,
        PlanDay(date=FIXED_TODAY, small=0, large=1, total_mg=150),
    ]
    mock_db.get_plan_day.return_value = None
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    cog = _make_cog()
    ix = _interaction()
    await cog.extra(ix, "large")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=0, large=1)
    ix.response.send_message.assert_awaited_once()


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_small_with_existing_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
) -> None:
    """With an existing actual (2s, 1L), /extra small -> 3s, 1L."""
    mock_date.today.return_value = FIXED_TODAY
    existing = PlanDay(date=FIXED_TODAY, small=2, large=1, total_mg=380)
    updated = PlanDay(date=FIXED_TODAY, small=3, large=1, total_mg=495)
    mock_db.get_actual.side_effect = [existing, updated]
    mock_db.get_plan_day.return_value = None
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    cog = _make_cog()
    ix = _interaction()
    await cog.extra(ix, "small")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=3, large=1)


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_large_with_existing_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
) -> None:
    """With an existing actual (2s, 1L), /extra large -> 2s, 2L."""
    mock_date.today.return_value = FIXED_TODAY
    existing = PlanDay(date=FIXED_TODAY, small=2, large=1, total_mg=380)
    updated = PlanDay(date=FIXED_TODAY, small=2, large=2, total_mg=530)
    mock_db.get_actual.side_effect = [existing, updated]
    mock_db.get_plan_day.return_value = None
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    cog = _make_cog()
    ix = _interaction()
    await cog.extra(ix, "large")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=2, large=2)
