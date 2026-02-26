# Yerba Mate Reduction Bot

A Discord bot that generates a personalized caffeine tapering plan from yerba mate, tracks your actual consumption, and sends daily reminders to keep you on track.

## How It Works

The bot creates a step-down schedule that gradually reduces caffeine intake by swapping large drinks (150mg) for small ones (115mg), then reducing total count. Each level is held for 2 days to let your body adjust. Steps smaller than 35mg are merged to avoid imperceptible changes.

**Example:** Starting from 3 large drinks (450mg), the plan tapers down over ~18 days:

```
2025-11-09  0S + 3L = 450mg
2025-11-11  1S + 2L = 415mg  (-35mg)
2025-11-13  2S + 1L = 380mg  (-35mg)
2025-11-15  3S + 0L = 345mg  (-35mg)
2025-11-17  0S + 2L = 300mg  (-45mg)
...
2025-11-25  1S + 0L = 115mg  (-35mg)
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/plan large:<int> small:<int>` | Generate a new tapering plan starting today |
| `/log large:<int> small:<int> date:<optional>` | Record actual consumption (default: today) |
| `/extra size:<large\|small>` | Add one extra drink to today's log |
| `/adjust keep:<optional bool>` | Recalculate plan based on most recent actual |
| `/status` | Show today's planned vs actual consumption |
| `/history weeks:<optional int>` | Show plan vs actual for past N weeks |

### `/adjust` modes

- **Default (`keep=False`):** Replans from your most recent actual consumption, generating a new tapering schedule starting tomorrow.
- **`keep=True`:** Keeps the existing plan trajectory and inserts catch-up days at your actual level to bridge back to the original schedule.

## Setup

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and add a bot
3. Enable the `applications.commands` scope
4. Invite the bot to your server

### 2. Configure Environment

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your-bot-token
PING_CHANNEL_ID=your-channel-id
```

`PING_CHANNEL_ID` is the channel where the bot sends daily 6am PST reminders.

### 3. Install and Run

```bash
pip install -r requirements.txt
python bot.py
```

## Project Structure

```
├── main.py           # Original standalone script
├── bot.py            # Bot entry point — setup, scheduler, run
├── planner.py        # Pure-function reduction algorithm
├── db.py             # SQLite persistence (yerba_mate.db)
├── commands.py       # Discord slash command cog
├── formatters.py     # Embed formatting helpers
├── requirements.txt  # discord.py, APScheduler, python-dotenv
└── .env              # DISCORD_TOKEN, PING_CHANNEL_ID
```

## Daily Reminder

The bot sends an embed to your configured channel every day at 6:00 AM Pacific with your target consumption for that day. If no plan exists, it prompts you to create one.

## Dependencies

- [discord.py](https://github.com/Rapptz/discord.py) — Discord API wrapper
- [APScheduler](https://github.com/agronholm/apscheduler) — Scheduled daily pings
- [python-dotenv](https://github.com/theskumar/python-dotenv) — Environment variable loading

## License

MIT
