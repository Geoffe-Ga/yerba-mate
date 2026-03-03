"""Tests for the /adjust command strategy choices (PR #8)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from planner import PlanDay

if TYPE_CHECKING:
    from typing import Any

FIXED_TODAY = date(2025, 7, 10)
TOMORROW = FIXED_TODAY + timedelta(days=1)


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
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """Replan strategy generates a new plan with skip_hold."""
    mock_date.today.return_value = FIXED_TODAY
    recent = _recent()
    mock_db.get_most_recent_actual.return_value = recent
    mock_gen.return_value = [
        PlanDay(date=TOMORROW, small=1, large=1, total_mg=265),
    ]
    mock_fmt.plan_embed.return_value = MagicMock()

    await cog.adjust.callback(cog, mock_interaction, "replan")

    mock_gen.assert_called_once_with(
        small=recent.small,
        large=recent.large,
        start_date=TOMORROW,
        skip_hold=True,
    )
    mock_db.replace_plan_from_date.assert_called_once()
    mock_interaction.response.send_message.assert_awaited_once()


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_no_recent_actual(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    _mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """With no actuals logged, /adjust sends an ephemeral error."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_most_recent_actual.return_value = None

    await cog.adjust.callback(cog, mock_interaction, "replan")

    mock_interaction.response.send_message.assert_awaited_once()
    call_kwargs = mock_interaction.response.send_message.call_args
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
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """Calling /adjust without strategy defaults to replan."""
    mock_date.today.return_value = FIXED_TODAY
    recent = _recent()
    mock_db.get_most_recent_actual.return_value = recent
    mock_gen.return_value = [
        PlanDay(date=TOMORROW, small=1, large=1, total_mg=265),
    ]
    mock_fmt.plan_embed.return_value = MagicMock()

    # Call without explicit strategy — should default to "replan"
    await cog.adjust.callback(cog, mock_interaction)

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
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """strategy='catchup' with no future plan sends an ephemeral error."""
    mock_date.today.return_value = FIXED_TODAY
    mock_db.get_most_recent_actual.return_value = _recent()
    mock_db.get_plan_days_from.return_value = []

    await cog.adjust.callback(cog, mock_interaction, "catchup")

    mock_interaction.response.send_message.assert_awaited_once()
    call_kwargs = mock_interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    assert "No future plan" in call_kwargs.args[0]


@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_catchup_inserts_hold_days(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """Catchup inserts hold days at actual level until plan reconverges."""
    mock_date.today.return_value = FIXED_TODAY
    recent = _recent(small=2, large=1)  # total_mg = 380

    # Future plan: first two days above actual, third matches
    jul11 = TOMORROW
    jul12 = TOMORROW + timedelta(days=1)
    jul13 = TOMORROW + timedelta(days=2)
    jul14 = TOMORROW + timedelta(days=3)
    future_plan = [
        PlanDay(date=jul11, small=3, large=2, total_mg=645),
        PlanDay(date=jul12, small=3, large=1, total_mg=495),
        PlanDay(date=jul13, small=2, large=1, total_mg=380),  # target
        PlanDay(date=jul14, small=1, large=1, total_mg=265),
    ]

    mock_db.get_most_recent_actual.return_value = recent
    mock_db.get_plan_days_from.return_value = future_plan
    mock_fmt.plan_embed.return_value = MagicMock()

    await cog.adjust.callback(cog, mock_interaction, "catchup")

    # Should have called replace_plan_from_date with catch-up + remaining
    mock_db.replace_plan_from_date.assert_called_once()
    combined = mock_db.replace_plan_from_date.call_args.args[0]

    # First two days are catch-up at actual level (380mg)
    assert combined[0].date == jul11
    assert combined[0].total_mg == recent.total_mg
    assert combined[1].date == jul12
    assert combined[1].total_mg == recent.total_mg

    # Remaining plan days follow (shifted by 0 in this case)
    assert combined[2].total_mg == 380
    assert combined[3].total_mg == 265

    mock_interaction.response.send_message.assert_awaited_once()


@patch("commands.generate_plan")
@patch("commands.formatters")
@patch("commands.db")
@patch("commands.date")
@patch("commands.timedelta", wraps=timedelta)
async def test_adjust_catchup_actual_below_plan_replans(
    _mock_td: MagicMock,
    mock_date: MagicMock,
    mock_db: MagicMock,
    mock_fmt: MagicMock,
    mock_gen: MagicMock,
    cog: Any,
    mock_interaction: MagicMock,
) -> None:
    """Catchup with actual below entire plan falls back to replan."""
    mock_date.today.return_value = FIXED_TODAY
    # Actual is low — below all future plan days
    recent = _recent(small=0, large=1)  # total_mg = 150

    future_plan = [
        PlanDay(date=TOMORROW, small=2, large=1, total_mg=380),
        PlanDay(
            date=TOMORROW + timedelta(days=1),
            small=1,
            large=1,
            total_mg=265,
        ),
    ]

    mock_db.get_most_recent_actual.return_value = recent
    mock_db.get_plan_days_from.return_value = future_plan
    mock_gen.return_value = [
        PlanDay(date=TOMORROW, small=0, large=0, total_mg=0),
    ]
    mock_fmt.plan_embed.return_value = MagicMock()

    await cog.adjust.callback(cog, mock_interaction, "catchup")

    # Should fall back to generate_plan since actual < all plan days
    mock_gen.assert_called_once_with(
        small=recent.small,
        large=recent.large,
        start_date=TOMORROW,
        skip_hold=True,
    )
    mock_db.replace_plan_from_date.assert_called_once()
    mock_interaction.response.send_message.assert_awaited_once()
