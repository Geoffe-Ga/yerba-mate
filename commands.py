"""Discord slash command cog for the yerba mate reduction bot."""

from __future__ import annotations

from datetime import date, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import db
import formatters
from planner import PlanDay, generate_plan


class YerbaCog(commands.Cog):
    """Slash commands for managing a yerba mate caffeine reduction plan."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # /plan
    # ------------------------------------------------------------------

    @app_commands.command(
        name="plan", description="Generate a new caffeine reduction plan from today"
    )
    @app_commands.describe(
        large="Number of large drinks per day", small="Number of small drinks per day"
    )
    async def plan(
        self, interaction: discord.Interaction, large: int, small: int
    ) -> None:
        """Generate and persist a reduction plan starting today."""
        today = date.today()
        plan = generate_plan(small=small, large=large, start_date=today)
        db.save_plan(plan)
        embed = formatters.plan_embed(plan)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /log
    # ------------------------------------------------------------------

    @app_commands.command(
        name="log", description="Record actual consumption for a date"
    )
    @app_commands.describe(
        large="Number of large drinks",
        small="Number of small drinks",
        date_str='Date: "today", "yesterday", or YYYY-MM-DD (default: today)',
    )
    async def log(
        self,
        interaction: discord.Interaction,
        large: int,
        small: int,
        date_str: str = "today",
    ) -> None:
        """Log actual consumption. Upserts into actuals table."""
        today = date.today()
        target = _parse_date(date_str, today)

        if target is None:
            await interaction.response.send_message(
                f"Invalid date: `{date_str}`. "
                "Use `today`, `yesterday`, or `YYYY-MM-DD`.",
                ephemeral=True,
            )
            return

        if target > today:
            await interaction.response.send_message(
                "Cannot log future dates.", ephemeral=True
            )
            return

        replaced = db.get_actual(target) is not None
        db.upsert_actual(target, small=small, large=large)
        actual = db.get_actual(target)
        assert actual is not None  # just upserted
        plan_day = db.get_plan_day(target)
        embed = formatters.log_confirmation_embed(actual, plan_day, replaced=replaced)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /extra
    # ------------------------------------------------------------------

    @app_commands.command(
        name="extra", description="Add one extra drink to today's actual"
    )
    @app_commands.describe(size="Size of the extra drink")
    @app_commands.choices(
        size=[
            app_commands.Choice(name="large", value="large"),
            app_commands.Choice(name="small", value="small"),
        ]
    )
    async def extra(self, interaction: discord.Interaction, size: str) -> None:
        """Add one extra drink to today's log."""
        today = date.today()
        actual = db.get_actual(today)

        if actual is None:
            sm, lg = 0, 0
        else:
            sm, lg = actual.small, actual.large

        if size == "large":
            lg += 1
        else:
            sm += 1

        db.upsert_actual(today, small=sm, large=lg)
        actual = db.get_actual(today)
        assert actual is not None  # just upserted
        plan_day = db.get_plan_day(today)
        embed = formatters.log_confirmation_embed(actual, plan_day, replaced=False)
        embed.title = f"Extra {size} added — {today}"
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /adjust
    # ------------------------------------------------------------------

    @app_commands.command(
        name="adjust",
        description="Recalculate plan based on most recent actual consumption",
    )
    @app_commands.describe(
        strategy="How to adjust: replan from scratch or catch up to existing plan"
    )
    @app_commands.choices(
        strategy=[
            app_commands.Choice(
                name="Replan — new reduction schedule from current level",
                value="replan",
            ),
            app_commands.Choice(
                name="Catch up — hold at current level then rejoin existing plan",
                value="catchup",
            ),
        ]
    )
    async def adjust(
        self,
        interaction: discord.Interaction,
        strategy: str = "replan",
    ) -> None:
        """Adjust the plan based on actual consumption."""
        recent = db.get_most_recent_actual()
        if recent is None:
            await interaction.response.send_message(
                "No actuals logged yet — use `/log` first.", ephemeral=True
            )
            return

        tomorrow = date.today() + timedelta(days=1)

        if strategy == "replan":
            # Regenerate plan reducing immediately from actual level
            new_plan = generate_plan(
                small=recent.small,
                large=recent.large,
                start_date=tomorrow,
                skip_hold=True,
            )
            db.replace_plan_from_date(new_plan, from_date=tomorrow)
            embed = formatters.plan_embed(new_plan)
            embed.title = "Plan Adjusted (replanned from actual)"
        else:
            # Keep existing trajectory, insert catch-up days
            future_plan = db.get_plan_days_from(tomorrow)
            if not future_plan:
                await interaction.response.send_message(
                    "No future plan days to adjust toward. "
                    "Use `/plan` to create a new plan.",
                    ephemeral=True,
                )
                return

            # Find the first future plan day that matches or is below actual level
            target_day = None
            for p in future_plan:
                if p.total_mg <= recent.total_mg:
                    target_day = p
                    break

            if target_day is None:
                # Actual is already below entire plan — just replan
                new_plan = generate_plan(
                    small=recent.small,
                    large=recent.large,
                    start_date=tomorrow,
                    skip_hold=True,
                )
                db.replace_plan_from_date(new_plan, from_date=tomorrow)
                embed = formatters.plan_embed(new_plan)
                embed.title = "Plan Adjusted (actual already below plan)"
            else:
                # Insert catch-up days at actual level, then shift remaining plan
                catch_up_days: list[date] = []
                d = tomorrow
                while d < target_day.date:
                    catch_up_days.append(d)
                    d += timedelta(days=1)

                # Build new plan: catch-up days at actual level + shifted remaining
                new_entries = [
                    PlanDay(
                        date=cd,
                        small=recent.small,
                        large=recent.large,
                        total_mg=recent.total_mg,
                    )
                    for cd in catch_up_days
                ]

                # Shift remaining plan days forward by number of catch-up days
                shift = len(catch_up_days) - (target_day.date - tomorrow).days
                remaining = [p for p in future_plan if p.date >= target_day.date]
                shifted = [
                    PlanDay(
                        date=p.date + timedelta(days=shift),
                        small=p.small,
                        large=p.large,
                        total_mg=p.total_mg,
                    )
                    for p in remaining
                ]

                combined = new_entries + shifted
                db.replace_plan_from_date(combined, from_date=tomorrow)
                embed = formatters.plan_embed(combined)
                embed.title = "Plan Adjusted (catch-up days inserted)"

        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /status
    # ------------------------------------------------------------------

    @app_commands.command(
        name="status", description="Show today's planned vs actual consumption"
    )
    async def status(self, interaction: discord.Interaction) -> None:
        """Show today's plan vs actual."""
        today = date.today()
        plan_day = db.get_plan_day(today)
        actual = db.get_actual(today)

        if plan_day is None and actual is None:
            await interaction.response.send_message(
                "No plan or actuals for today. Use `/plan` to get started.",
                ephemeral=True,
            )
            return

        embed = formatters.status_embed(plan_day, actual, today)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /history
    # ------------------------------------------------------------------

    @app_commands.command(
        name="history", description="Show planned vs actual for past N weeks"
    )
    @app_commands.describe(weeks="Number of weeks to show (default: 4)")
    async def history(self, interaction: discord.Interaction, weeks: int = 4) -> None:
        """Show history of plan vs actual consumption."""
        today = date.today()
        from_date = today - timedelta(weeks=weeks)

        plan_list = db.get_plan_range(from_date, today)
        actual_list = db.get_actuals_range(from_date, today)

        plan_map = {p.date: p for p in plan_list}
        actual_map = {a.date: a for a in actual_list}

        if not plan_map and not actual_map:
            await interaction.response.send_message(
                f"No data for the past {weeks} weeks.", ephemeral=True
            )
            return

        embed = formatters.history_embed(plan_map, actual_map, from_date, today)
        await interaction.response.send_message(embed=embed)


def _parse_date(date_str: str, today: date) -> date | None:
    """Parse a date string: 'today', 'yesterday', or YYYY-MM-DD."""
    lower = date_str.strip().lower()
    if lower == "today":
        return today
    if lower == "yesterday":
        return today - timedelta(days=1)
    try:
        return date.fromisoformat(date_str.strip())
    except ValueError:
        return None


async def setup(bot: commands.Bot) -> None:
    """Add the cog to the bot."""
    await bot.add_cog(YerbaCog(bot))
