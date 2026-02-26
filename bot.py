"""Entry point for the yerba mate reduction Discord bot."""

from __future__ import annotations

import os
from datetime import date

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands
from dotenv import load_dotenv

import db
import formatters

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
PING_CHANNEL_ID = int(os.environ["PING_CHANNEL_ID"])

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler()


async def daily_ping() -> None:
    """Send daily target reminder to the configured channel."""
    channel = bot.get_channel(PING_CHANNEL_ID)
    if channel is None or not isinstance(channel, discord.TextChannel):
        return
    today = date.today()
    plan_day = db.get_plan_day(today)
    embed = formatters.daily_ping_embed(plan_day, today)
    await channel.send(embed=embed)


@bot.event
async def on_ready() -> None:
    """Initialize database, load cog, sync commands, start scheduler."""
    db.init_db()
    await bot.load_extension("commands")
    await bot.tree.sync()

    scheduler.add_job(
        daily_ping,
        CronTrigger(hour=6, minute=0, timezone="US/Pacific"),
        id="daily_ping",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    print(f"Bot ready as {bot.user} — commands synced, scheduler started.")


if __name__ == "__main__":
    bot.run(TOKEN)
