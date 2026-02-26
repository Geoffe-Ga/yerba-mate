"""Discord embed formatting helpers for the yerba mate bot."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from planner import PlanDay

# Target ~34 chars wide for mobile Discord code blocks.
# Date(5) Sm(3) Lg(3) mg(4) Drop(4) + separators = ~34
_HDR = f"{'Date':<5} {'Sm':>2} {'Lg':>2} {'mg':>4} {'Drop':>4}"
_SEP = "\u2500" * 22


def _format_drinks(small: int, large: int) -> str:
    """Format drink counts as readable text."""
    parts = []
    if small:
        parts.append(f"{small} small")
    if large:
        parts.append(f"{large} large")
    return ", ".join(parts) if parts else "none"


def _ds(d: date) -> str:
    """Short date: MM/DD."""
    return d.strftime("%m/%d")


def _row(d: date, small: int, large: int, mg: int, drop: str = "") -> str:
    """Format one row in the standard table layout."""
    return f"{_ds(d):<5} {small:>2} {large:>2} {mg:>4} {drop:>4}"


def _make_table(lines: list[str]) -> str:
    """Wrap lines in a Discord code block."""
    return "```\n" + "\n".join(lines) + "\n```"


def plan_embed(plan: list[PlanDay]) -> discord.Embed:
    """Format the full tapering plan as a one-row-per-day table."""
    embed = discord.Embed(
        title="Yerba Mate Reduction Plan",
        color=discord.Color.green(),
    )

    lines = [_HDR, _SEP]
    prev_mg = 0
    for p in plan:
        drop = ""
        if prev_mg and prev_mg != p.total_mg:
            diff = prev_mg - p.total_mg
            drop = f"-{diff}" if diff > 0 else f"+{-diff}"
        prev_mg = p.total_mg
        lines.append(_row(p.date, p.small, p.large, p.total_mg, drop))

    table = _make_table(lines)

    start = plan[0].date
    end = plan[-1].date
    embed.description = table
    embed.set_footer(text=f"{len(plan)} days \u2014 {start} to {end}")
    return embed


def status_embed(
    plan_day: PlanDay | None,
    actual: PlanDay | None,
    today: date,
) -> discord.Embed:
    """Format today's status as a compact table."""
    embed = discord.Embed(
        title=f"Status \u2014 {today.strftime('%b %d')}",
        color=discord.Color.blue(),
    )

    hdr = f"{'':>6} {'Sm':>2} {'Lg':>2} {'mg':>4}"
    lines = [hdr, "\u2500" * 17]

    if plan_day:
        lines.append(
            f"{'Plan':>6} {plan_day.small:>2} "
            f"{plan_day.large:>2} {plan_day.total_mg:>4}"
        )
    else:
        lines.append(f"{'Plan':>6}  (no plan)")

    if actual:
        lines.append(
            f"{'Actual':>6} {actual.small:>2} {actual.large:>2} {actual.total_mg:>4}"
        )
    else:
        lines.append(f"{'Actual':>6}  (not logged)")

    if plan_day and actual:
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        lines.append(f"{'Delta':>6} {'':>2} {'':>2} {sign}{delta:>3}")

    embed.description = _make_table(lines)
    return embed


def log_confirmation_embed(
    actual: PlanDay, plan_day: PlanDay | None, replaced: bool
) -> discord.Embed:
    """Confirmation embed after logging consumption."""
    title = f"Logged \u2014 {actual.date.strftime('%b %d')}"
    if replaced:
        title += " (updated)"
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold() if replaced else discord.Color.green(),
    )

    hdr = f"{'':>6} {'Sm':>2} {'Lg':>2} {'mg':>4}"
    lines = [hdr, "\u2500" * 17]
    lines.append(
        f"{'Actual':>6} {actual.small:>2} {actual.large:>2} {actual.total_mg:>4}"
    )
    if plan_day:
        lines.append(
            f"{'Plan':>6} {plan_day.small:>2} "
            f"{plan_day.large:>2} {plan_day.total_mg:>4}"
        )
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        lines.append(f"{'Delta':>6} {'':>2} {'':>2} {sign}{delta:>3}")

    embed.description = _make_table(lines)
    return embed


def history_embed(
    plan_days: dict[date, PlanDay],
    actuals: dict[date, PlanDay],
    from_date: date,
    to_date: date,
) -> discord.Embed:
    """Format history table of plan vs actual, one row per day."""
    embed = discord.Embed(
        title=f"History \u2014 {from_date} to {to_date}",
        color=discord.Color.purple(),
    )
    lines = [
        f"{'Date':<5} {'Plan':>4} {'Real':>4} {'Delta':>5}",
        "\u2500" * 21,
    ]

    d = from_date
    while d <= to_date:
        plan = plan_days.get(d)
        actual = actuals.get(d)
        p_str = str(plan.total_mg) if plan else "\u00b7"
        a_str = str(actual.total_mg) if actual else "\u00b7"
        if plan and actual:
            delta = actual.total_mg - plan.total_mg
            sign = "+" if delta > 0 else ""
            d_str = f"{sign}{delta}"
        else:
            d_str = "\u00b7"
        lines.append(f"{_ds(d):<5} {p_str:>4} {a_str:>4} {d_str:>5}")
        d += timedelta(days=1)

    table = _make_table(lines)
    if len(table) <= 4096:
        embed.description = table
    else:
        embed.description = table[:4093] + "```"

    return embed


def daily_ping_embed(plan_day: PlanDay | None, today: date) -> discord.Embed:
    """Format the daily reminder ping."""
    if plan_day:
        drinks = _format_drinks(plan_day.small, plan_day.large)
        embed = discord.Embed(
            title=f"Today's Target \u2014 {today.strftime('%b %d')}",
            description=f"**{drinks}** \u2014 **{plan_day.total_mg} mg**",
            color=discord.Color.teal(),
        )
    else:
        embed = discord.Embed(
            title=f"No Plan for {today.strftime('%b %d')}",
            description="Use `/plan` to create a reduction plan.",
            color=discord.Color.light_grey(),
        )
    return embed
