"""Tests for the discord-free formatters module (issue #17).

The Discord bot is retired; formatters now return plain FormattedMessage
data that RubotPaul renders itself. These tests pin the table layouts the
old embeds produced.
"""

from __future__ import annotations

from datetime import date, timedelta

from helpers import make_plan_day

from formatters import (
    FormattedMessage,
    daily_ping_message,
    history_message,
    log_confirmation_message,
    plan_message,
    status_message,
)

TODAY = date(2025, 6, 15)


def _plan(days: int = 2) -> list:
    """A short descending plan starting TODAY."""
    return [
        make_plan_day(TODAY + timedelta(days=i), small=0, large=3 - (i > 0))
        for i in range(days)
    ]


# ---------------------------------------------------------------------------
# plan_message
# ---------------------------------------------------------------------------


def test_plan_message_table_and_footer() -> None:
    """Full plan renders one row per day with drop column and footer."""
    plan = _plan()
    message = plan_message(plan)
    assert isinstance(message, FormattedMessage)
    assert message.title == "Yerba Mate Reduction Plan"
    assert message.body.startswith("```\n")
    assert message.body.endswith("\n```")
    assert "06/15" in message.body
    assert "06/16" in message.body
    assert "-150" in message.body  # 3 large -> 2 large drop
    assert message.footer == f"2 days — {plan[0].date} to {plan[-1].date}"


# ---------------------------------------------------------------------------
# status_message
# ---------------------------------------------------------------------------


def test_status_message_with_plan_and_actual_shows_delta() -> None:
    """Plan + actual rows produce Plan, Actual, and Delta lines."""
    plan_day = make_plan_day(TODAY, large=2)
    actual = make_plan_day(TODAY, large=3)
    message = status_message(plan_day, actual, TODAY)
    assert message.title == f"Status — {TODAY.strftime('%b %d')}"
    assert "Plan" in message.body
    assert "Actual" in message.body
    assert "+150" in message.body


def test_status_message_handles_missing_sides() -> None:
    """Missing plan or actual rows degrade to placeholder text."""
    message = status_message(None, None, TODAY)
    assert "(no plan)" in message.body
    assert "(not logged)" in message.body
    assert "Delta" not in message.body


# ---------------------------------------------------------------------------
# log_confirmation_message
# ---------------------------------------------------------------------------


def test_log_confirmation_message_marks_updates() -> None:
    """replaced=True adds the (updated) marker to the title."""
    actual = make_plan_day(TODAY, small=1)
    message = log_confirmation_message(actual, None, replaced=True)
    assert message.title.endswith("(updated)")
    assert "Actual" in message.body
    assert "Delta" not in message.body


def test_log_confirmation_message_with_plan_shows_delta() -> None:
    """A plan row adds Plan and signed Delta lines."""
    actual = make_plan_day(TODAY, small=2)
    plan_day = make_plan_day(TODAY, small=3)
    message = log_confirmation_message(actual, plan_day, replaced=False)
    assert "(updated)" not in message.title
    assert "Plan" in message.body
    assert "-115" in message.body


# ---------------------------------------------------------------------------
# history_message
# ---------------------------------------------------------------------------


def test_history_message_marks_missing_days() -> None:
    """Days with only one side show the middle-dot placeholder."""
    plan_days = {TODAY: make_plan_day(TODAY, large=2)}
    actuals = {TODAY + timedelta(days=1): make_plan_day(TODAY, large=1)}
    message = history_message(plan_days, actuals, TODAY, TODAY + timedelta(days=1))
    assert message.title == f"History — {TODAY} to {TODAY + timedelta(days=1)}"
    assert "·" in message.body


def test_history_message_truncates_very_long_tables() -> None:
    """Bodies past the Discord 4096 limit are truncated but stay fenced."""
    plan_days = {
        TODAY + timedelta(days=i): make_plan_day(TODAY + timedelta(days=i), large=2)
        for i in range(400)
    }
    message = history_message(plan_days, {}, TODAY, TODAY + timedelta(days=399))
    assert len(message.body) <= 4096
    assert message.body.endswith("```")


# ---------------------------------------------------------------------------
# daily_ping_message
# ---------------------------------------------------------------------------


def test_daily_ping_message_with_plan() -> None:
    """A plan day yields the day's target drinks and total mg."""
    plan_day = make_plan_day(TODAY, small=1, large=2)
    message = daily_ping_message(plan_day, TODAY)
    assert message.title == f"Today's Target — {TODAY.strftime('%b %d')}"
    assert "1 small, 2 large" in message.body
    assert f"{plan_day.total_mg} mg" in message.body


def test_daily_ping_message_without_plan() -> None:
    """No plan yields the nudge to create one."""
    message = daily_ping_message(None, TODAY)
    assert message.title == f"No Plan for {TODAY.strftime('%b %d')}"
    assert "create a reduction plan" in message.body
