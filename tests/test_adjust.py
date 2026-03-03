"""Tests for the /adjust command strategy choices (PR #8)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is importable (conftest.py handles discord stubs)
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from commands import YerbaCog  # noqa: E402
from planner import PlanDay  # noqa: E402

FIXED_TODAY = date(2025, 7, 10)
TOMORROW = FIXED_TODAY + timedelta(days=1)


def _make_cog() -> YerbaCog:
    return YerbaCog(MagicMock())


def _interaction() -> MagicMock:
    ix = MagicMock()
    ix.response = AsyncMock()
    ix.response.send_message = AsyncMock()
    return ix


def _recent(*, small: int = 2, large: int = 1) -> PlanDay:
    return PlanDay(
        date=FIXED_TODAY,
        small=small,
        large=large,
        total_mg=(115 * small) + (150 * large),
    )


@patch("commands.generate_plan")
@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_replan_strategy(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    mock_gen: MagicMock,
) -> None:
    """Replan strategy generates a new plan with skip_hold."""
    mock_date.today.return_value = FIXED_TODAY
    recent = _recent()
    mock_db.get_most_recent_actual.return_value = recent
    mock_gen.return_value = [PlanDay(date=TOMORROW, small=1, large=1, total_mg=265)]
    mock_fmt.plan_embed.return_value = MagicMock()

    cog = _make_cog()
    ix = _interaction()
    await cog.adjust(ix, "replan")

    mock_gen.assert_called_once_with(
        small=recent.small,
        large=recent.large,
        start_date=TOMORROW,
        skip_hold=True,
    )
    mock_db.replace_plan_from_date.assert_called_once()
    ix.response.send_message.assert_awaited_once()


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_no_recent_actual(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    _mock_fmt: MagicMock,
) -> None:
    """With no actuals logged, /adjust sends an ephemeral error."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_most_recent_actual.return_value = None

    cog = _make_cog()
    ix = _interaction()
    await cog.adjust(ix, "replan")

    ix.response.send_message.assert_awaited_once()
    call_kwargs = ix.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@patch("commands.generate_plan")
@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_default_strategy_is_replan(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    mock_gen: MagicMock,
) -> None:
    """Calling /adjust without strategy defaults to replan."""
    mock_date.today.return_value = FIXED_TODAY
    recent = _recent()
    mock_db.get_most_recent_actual.return_value = recent
    mock_gen.return_value = [PlanDay(date=TOMORROW, small=1, large=1, total_mg=265)]
    mock_fmt.plan_embed.return_value = MagicMock()

    cog = _make_cog()
    ix = _interaction()
    # Call without explicit strategy — should default to "replan"
    await cog.adjust(ix)

    mock_gen.assert_called_once_with(
        small=recent.small,
        large=recent.large,
        start_date=TOMORROW,
        skip_hold=True,
    )


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_catchup_no_future_plan(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    _mock_fmt: MagicMock,
) -> None:
    """strategy='catchup' with no future plan sends an ephemeral error."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_most_recent_actual.return_value = _recent()
    mock_db.get_plan_days_from.return_value = []

    cog = _make_cog()
    ix = _interaction()
    await cog.adjust(ix, "catchup")

    ix.response.send_message.assert_awaited_once()
    call_kwargs = ix.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    assert "No future plan" in call_kwargs.args[0]
