"""Tests for the /extra command baseline behaviour (PR #6)."""

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
async def test_extra_small_no_prior_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """With no logged actual, /extra small starts from 0 and adds 1 small."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_actual.side_effect = [
        None,
        PlanDay(date=FIXED_TODAY, small=1, large=0, total_mg=115),
    ]
    mock_db.get_plan_day.return_value = None
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    await cog.extra.callback(cog, mock_interaction, "small")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=1, large=0)
    mock_interaction.response.send_message.assert_awaited_once()


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_large_no_prior_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """With no logged actual, /extra large starts from 0 and adds 1 large."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_actual.side_effect = [
        None,
        PlanDay(date=FIXED_TODAY, small=0, large=1, total_mg=150),
    ]
    mock_db.get_plan_day.return_value = None
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    await cog.extra.callback(cog, mock_interaction, "large")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=0, large=1)
    mock_interaction.response.send_message.assert_awaited_once()


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_small_with_existing_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """With an existing actual (2s, 1L), /extra small -> 3s, 1L."""
    mock_date.today.return_value = FIXED_TODAY
    existing = PlanDay(date=FIXED_TODAY, small=2, large=1, total_mg=380)
    updated = PlanDay(date=FIXED_TODAY, small=3, large=1, total_mg=495)
    mock_db.get_actual.side_effect = [existing, updated]
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    await cog.extra.callback(cog, mock_interaction, "small")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=3, large=1)


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
async def test_extra_large_with_existing_actual(
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """With an existing actual (2s, 1L), /extra large -> 2s, 2L."""
    mock_date.today.return_value = FIXED_TODAY
    existing = PlanDay(date=FIXED_TODAY, small=2, large=1, total_mg=380)
    updated = PlanDay(date=FIXED_TODAY, small=2, large=2, total_mg=530)
    mock_db.get_actual.side_effect = [existing, updated]
    mock_fmt.log_confirmation_embed.return_value = MagicMock()

    await cog.extra.callback(cog, mock_interaction, "large")

    mock_db.upsert_actual.assert_called_once_with(FIXED_TODAY, small=2, large=2)
