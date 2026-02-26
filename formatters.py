"""Discord embed formatting helpers for the yerba mate bot."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from planner import PlanDay

# Shared column layout used by plan, history, and status tables.
# Date(10) + Small(7) + Large(7) + mg(6) + Drop(6) = 40 chars
_HDR = f"{'Date':<10}  {'Small':>5}  {'Large':>5}  {'mg':>5}  {'Drop':>5}"
_SEP = "\u2500" * 40


def _format_drinks(small: int, large: int) -> str:
    """Format drink counts as readable text."""
    parts = []
    if small:
        parts.append(f"{small} small")
    if large:
        parts.append(f"{large} large")
    return ", ".join(parts) if parts else "none"


def _row(d: date, small: int, large: int, mg: int, drop: str = "") -> str:
    """Format one row in the standard table layout."""
    ds = d.strftime("%b %d")
    return f"{ds:<10}  {small:>5}  {large:>5}  {mg:>5}  {drop:>5}"


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
            drop = f"-{prev_mg - p.total_mg}"
        prev_mg = p.total_mg
        lines.append(_row(p.date, p.small, p.large, p.total_mg, drop))

    table = _make_table(lines)

    start = plan[0].date
    end = plan[-1].date
    embed.description = table
    embed.set_footer(text=f"{len(plan)} days \u2014 {start} to {end}")
    return embed


def status_embed(
    plan_day: PlanDay | None, actual: PlanDay | None, today: date
) -> discord.Embed:
    """Format today's status as a compact table."""
    embed = discord.Embed(
        title=f"Status \u2014 {today.strftime('%b %d, %Y')}",
        color=discord.Color.blue(),
    )

    lines = [f"{'':>8}  {'Small':>5}  {'Large':>5}  {'mg':>5}", "\u2500" * 28]

    if plan_day:
        lines.append(
            f"{'Plan':>8}  {plan_day.small:>5}  "
            f"{plan_day.large:>5}  {plan_day.total_mg:>5}"
        )
    else:
        lines.append(f"{'Plan':>8}{'(no plan)':>20}")

    if actual:
        lines.append(
            f"{'Actual':>8}  {actual.small:>5}  {actual.large:>5}  {actual.total_mg:>5}"
        )
    else:
        lines.append(f"{'Actual':>8}{'(not logged)':>20}")

    if plan_day and actual:
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        lines.append("")
        lines.append(f"{'Delta':>8}  {'':>5}  {'':>5}  {sign}{delta:>4}")

    embed.description = _make_table(lines)
    return embed


def log_confirmation_embed(
    actual: PlanDay, plan_day: PlanDay | None, replaced: bool
) -> discord.Embed:
    """Confirmation embed after logging consumption."""
    title = f"Logged \u2014 {actual.date.strftime('%b %d, %Y')}"
    if replaced:
        title += " (updated)"
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold() if replaced else discord.Color.green(),
    )

    lines = [f"{'':>8}  {'Small':>5}  {'Large':>5}  {'mg':>5}", "\u2500" * 28]
    lines.append(
        f"{'Actual':>8}  {actual.small:>5}  {actual.large:>5}  {actual.total_mg:>5}"
    )
    if plan_day:
        lines.append(
            f"{'Plan':>8}  {plan_day.small:>5}  "
            f"{plan_day.large:>5}  {plan_day.total_mg:>5}"
        )
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        lines.append("")
        lines.append(f"{'Delta':>8}  {'':>5}  {'':>5}  {sign}{delta:>4}")

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
        f"{'Date':<10}  {'Plan':>5}  {'Actual':>6}  {'Delta':>5}",
        "\u2500" * 31,
    ]

    d = from_date
    while d <= to_date:
        plan = plan_days.get(d)
        actual = actuals.get(d)
        plan_str = str(plan.total_mg) if plan else "\u00b7"
        actual_str = str(actual.total_mg) if actual else "\u00b7"
        if plan and actual:
            delta = actual.total_mg - plan.total_mg
            sign = "+" if delta > 0 else ""
            delta_str = f"{sign}{delta}"
        else:
            delta_str = "\u00b7"
        ds = d.strftime("%b %d")
        lines.append(f"{ds:<10}  {plan_str:>5}  {actual_str:>6}  {delta_str:>5}")
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
