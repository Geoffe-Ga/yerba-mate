"""Tests for the /plan show subcommand."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from planner import PlanDay

if TYPE_CHECKING:
    from typing import Any

FIXED_TODAY = date(2025, 6, 15)


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_plan_show_no_plan(
    mock_date: MagicMock,
    mock_db: MagicMock,
    _mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """When no plan exists, /plan show sends an ephemeral hint."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_plan_days_from.return_value = []

    await cog.plan_show.callback(cog, mock_interaction)

    mock_db.get_plan_days_from.assert_called_once_with(FIXED_TODAY)
    mock_interaction.response.send_message.assert_awaited_once_with(
        "No plan exists. Use `/plan create` to get started.",
        ephemeral=True,
    )


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_plan_show_with_plan(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """When a plan exists, /plan show sends an embed with remaining days."""
    mock_date.today.return_value = FIXED_TODAY
    plan_days = [
        PlanDay(date=FIXED_TODAY, small=2, large=1, total_mg=380),
        PlanDay(date=date(2025, 6, 16), small=2, large=1, total_mg=380),
    ]
    mock_db.get_plan_days_from.return_value = plan_days
    fake_embed = MagicMock()
    mock_fmt.plan_embed.return_value = fake_embed

    await cog.plan_show.callback(cog, mock_interaction)

    mock_fmt.plan_embed.assert_called_once_with(plan_days)
    assert fake_embed.title == "Current Plan (from today)"
    mock_interaction.response.send_message.assert_awaited_once_with(embed=fake_embed)
