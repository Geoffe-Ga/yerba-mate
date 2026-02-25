"""Discord embed formatting helpers for the yerba mate bot."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from planner import PlanDay


def plan_embed(plan: list[PlanDay]) -> discord.Embed:
    """Format the full tapering plan as an embed."""
    embed = discord.Embed(
        title="Yerba Mate Reduction Plan",
        color=discord.Color.green(),
    )
    lines = []
    for p in plan:
        lines.append(f"`{p.date}` — {p.small}S + {p.large}L = **{p.total_mg} mg**")

    # Discord embed field value limit is 1024 chars; split if needed
    chunk = "\n".join(lines)
    if len(chunk) <= 1024:
        embed.add_field(name="Schedule", value=chunk, inline=False)
    else:
        # Split into multiple fields
        current: list[str] = []
        current_len = 0
        part = 1
        for line in lines:
            if current_len + len(line) + 1 > 1024:
                embed.add_field(
                    name=f"Schedule (part {part})",
                    value="\n".join(current),
                    inline=False,
                )
                current = []
                current_len = 0
                part += 1
            current.append(line)
            current_len += len(line) + 1
        if current:
            embed.add_field(
                name=f"Schedule (part {part})", value="\n".join(current), inline=False
            )

    start = plan[0].date
    end = plan[-1].date
    embed.set_footer(text=f"{len(plan)} days — {start} to {end}")
    return embed


def status_embed(
    plan_day: PlanDay | None, actual: PlanDay | None, today: date
) -> discord.Embed:
    """Format today's status: plan vs actual."""
    embed = discord.Embed(title=f"Status for {today}", color=discord.Color.blue())

    if plan_day:
        embed.add_field(
            name="Plan",
            value=f"{plan_day.small}S + {plan_day.large}L = {plan_day.total_mg} mg",
            inline=True,
        )
    else:
        embed.add_field(name="Plan", value="No plan for today", inline=True)

    if actual:
        embed.add_field(
            name="Actual",
            value=f"{actual.small}S + {actual.large}L = {actual.total_mg} mg",
            inline=True,
        )
    else:
        embed.add_field(name="Actual", value="Not logged yet", inline=True)

    if plan_day and actual:
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        embed.add_field(name="Delta", value=f"{sign}{delta} mg", inline=True)

    return embed


def log_confirmation_embed(
    actual: PlanDay, plan_day: PlanDay | None, replaced: bool
) -> discord.Embed:
    """Confirmation embed after logging consumption."""
    embed = discord.Embed(
        title=f"Logged for {actual.date}",
        color=discord.Color.gold() if replaced else discord.Color.green(),
    )
    embed.add_field(
        name="Actual",
        value=f"{actual.small}S + {actual.large}L = {actual.total_mg} mg",
        inline=True,
    )
    if plan_day:
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        embed.add_field(name="vs Plan", value=f"{sign}{delta} mg", inline=True)
    if replaced:
        embed.set_footer(text="(replaced previous entry)")
    return embed


def history_embed(
    plan_days: dict[date, PlanDay],
    actuals: dict[date, PlanDay],
    from_date: date,
    to_date: date,
) -> discord.Embed:
    """Format history table of plan vs actual."""
    embed = discord.Embed(
        title=f"History: {from_date} to {to_date}",
        color=discord.Color.purple(),
    )
    lines = ["```"]
    lines.append(f"{'Date':<12} {'Plan':>7} {'Actual':>7} {'Delta':>7}")
    lines.append("-" * 36)

    d = from_date
    while d <= to_date:
        plan = plan_days.get(d)
        actual = actuals.get(d)
        plan_str = f"{plan.total_mg}" if plan else "-"
        actual_str = f"{actual.total_mg}" if actual else "-"
        if plan and actual:
            delta = actual.total_mg - plan.total_mg
            sign = "+" if delta > 0 else ""
            delta_str = f"{sign}{delta}"
        else:
            delta_str = "-"
        lines.append(f"{d!s:<12} {plan_str:>7} {actual_str:>7} {delta_str:>7}")
        d += timedelta(days=1)

    lines.append("```")
    chunk = "\n".join(lines)

    # Split if too long for embed field
    if len(chunk) <= 1024:
        embed.add_field(name="Daily Breakdown", value=chunk, inline=False)
    else:
        embed.description = chunk[:4096]

    return embed


def daily_ping_embed(plan_day: PlanDay | None, today: date) -> discord.Embed:
    """Format the daily reminder ping."""
    if plan_day:
        embed = discord.Embed(
            title=f"Today's Target — {today}",
            description=(
                f"**{plan_day.small}** small + "
                f"**{plan_day.large}** large = "
                f"**{plan_day.total_mg} mg**"
            ),
            color=discord.Color.teal(),
        )
    else:
        embed = discord.Embed(
            title=f"No Plan for {today}",
            description="Use `/plan` to create a reduction plan.",
            color=discord.Color.light_grey(),
        )
    return embed
