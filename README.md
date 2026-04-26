# Yerba Mate Reduction Bot

> Step down. Don't crash.

A Discord bot for the **Conscious Biohacker** who wants to reduce caffeine intake from yerba mate **without triggering withdrawal symptoms** — the headaches, brain fog, fatigue, and irritability that come from quitting cold turkey.

## Mission

Caffeine withdrawal is a real pharmacological event. The standard literature (and lived experience) shows that abrupt reductions of more than ~25% of daily intake can trigger 2–9 days of unpleasant symptoms. The *Conscious Biohacker* approach is to **taper gradually** — small, regular drops your adenosine receptors can adapt to — instead of quitting outright.

This bot exists because doing that taper by hand is annoying:

1. You have to compute a step-down schedule that never drops too fast.
2. You have to remember your daily target every morning.
3. You inevitably miss a day or drink extra, and the plan needs to recover gracefully.
4. You want to look back and see whether you actually stuck to the plan.

The bot automates all four. It generates a personalized tapering plan from your current intake, pings you each morning at 6 AM Pacific with that day's target, lets you log actual consumption (including extras, slips, and adjustments), and recalibrates the plan when life happens.

## How the Reduction Algorithm Works

Yerba mate at our reference café comes in two sizes:

| Size  | Caffeine |
|-------|---------:|
| Small | 115 mg   |
| Large | 150 mg   |

Starting from `(L large + S small)` drinks per day, the algorithm steps down by:

1. **Swap a large for a small** (–35 mg per swap), repeating until all drinks are smalls.
2. **Drop the count** — once at all smalls, replace `N small` with `(N–1) large`, then repeat the swap loop.
3. **Hold each level for 2 days** so adenosine receptor density adjusts before the next drop.
4. **Merge tiny steps** — if a transition would change caffeine by less than 35 mg, the previous level is overwritten so no step is imperceptible (and no day feels wasted).
5. **Stop at 115 mg** (one small) — the floor below which we declare victory.

### Example: starting from 3 large (450 mg)

```
2025-11-09  0S + 3L = 450mg
2025-11-11  1S + 2L = 415mg  (-35mg)
2025-11-13  2S + 1L = 380mg  (-35mg)
2025-11-15  3S + 0L = 345mg  (-35mg)
2025-11-17  0S + 2L = 300mg  (-45mg)
...
2025-11-25  1S + 0L = 115mg  (-35mg)
```

About 18 days from `(0S + 3L)` to a single small drink. Total caffeine load drops by ~75% with every step well below the withdrawal threshold.

## Slash Command Reference

The bot exposes its behavior entirely through Discord slash commands. Once invited to a server, the commands appear in the autocomplete drawer.

### `/plan create large:<int> small:<int>`
Generates and persists a fresh tapering plan starting **today**, replacing any future plan days.

### `/plan show`
Displays the remaining plan from today onward as a Discord embed.

### `/log large:<int> small:<int> date_str:<optional>`
Records actual consumption. `date_str` accepts `today` (default), `yesterday`, or `YYYY-MM-DD`. Future dates are rejected. Re-logging the same date overwrites the previous entry.

### `/extra size:<large|small>`
Increments today's actual log by one drink. Useful when you grab a "just one more" without wanting to retype the full count.

### `/adjust strategy:<replan|catchup>`
Recalibrates the plan based on your most recent actual consumption.

| Strategy | Behavior |
|----------|----------|
| `replan` *(default)* | Generate a new tapering schedule starting tomorrow from your most recent actual level. |
| `catchup` | Hold at the current actual level for as many days as needed, then rejoin the original plan when it dips down to that level. |

Use `replan` if you've truly fallen behind. Use `catchup` if you had a one-off slip and want to preserve the original schedule.

### `/status`
Shows today's planned vs actual consumption with the delta.

### `/history weeks:<int>`
Shows planned vs actual for the past N weeks (default 4) as a one-row-per-day table.

### Daily Reminder (automatic)
Every day at **06:00 US/Pacific**, the bot posts an embed to `PING_CHANNEL_ID` with the day's target consumption. If no plan exists, it nudges you to create one.

## Architecture

The codebase is small (~600 LOC) and deliberately split into single-purpose modules with a strict dependency graph:

```
bot.py ──────┐
             ├──► commands.py ──► planner.py  (pure)
             │         │
             │         └──► db.py    ──► PostgreSQL
             │         │
             │         └──► formatters.py
             │
             └──► db.py        ──► PostgreSQL
             └──► formatters.py
```

| Module             | Responsibility                                                          | Side effects |
|--------------------|-------------------------------------------------------------------------|:------------:|
| `bot.py`           | Discord client setup, scheduler, daily ping, cog loading                | Network, time |
| `commands.py`      | Slash command cog: parses interactions, orchestrates planner + db + formatters | Network, DB |
| `planner.py`       | Pure-function tapering algorithm                                        | None         |
| `db.py`            | PostgreSQL connection pool + plan/actuals persistence                   | DB           |
| `formatters.py`    | Discord `Embed` builders (tables, deltas, status)                       | None         |
| `main.py`          | Original standalone TSV-printing script (kept for reference / cron use) | stdout       |

The dependency graph is acyclic: `planner` and `formatters` are pure and free of I/O, `db` knows nothing about Discord, and `commands` is the only place where domain logic, persistence, and presentation meet.

### Data model

Two tables, both keyed by date:

```sql
CREATE TABLE plan_days (
    date     DATE PRIMARY KEY,
    small    INTEGER NOT NULL,
    large    INTEGER NOT NULL,
    total_mg INTEGER NOT NULL
);

CREATE TABLE actuals (
    date     DATE PRIMARY KEY,
    small    INTEGER NOT NULL,
    large    INTEGER NOT NULL,
    total_mg INTEGER NOT NULL
);
```

The same `PlanDay` dataclass is reused for both plan rows and actual rows, since the shape is identical. `total_mg` is denormalized so the database can be queried for trends without recomputing.

`save_plan` / `replace_plan_from_date` always treat the plan as **append-from-cutoff**: history before the cutoff is preserved so the `/history` command can show what *was* planned even after a `/adjust`.

### Scheduling

Daily reminders run on `APScheduler`'s `AsyncIOScheduler` co-located with the Discord event loop, with a `CronTrigger` pinned to `US/Pacific` and a 1-hour `misfire_grace_time` so a brief restart doesn't skip the morning ping.

## Code & Technology Choices

| Choice | Why |
|--------|-----|
| **Python 3.12** | Modern type syntax, `dataclass(slots=True)`, no FFI complications. Pinned via `runtime.txt` for Heroku-style deploys. |
| **discord.py 2.x** | First-class slash command support via `app_commands`. Cog pattern keeps `bot.py` tiny. |
| **APScheduler** | Async-native scheduler that lives in the same event loop as the bot — no second process, no cron container. |
| **PostgreSQL via psycopg2** | Persistent across restarts (Discord bots restart often). The `SimpleConnectionPool` keeps connection setup cheap without an ORM. |
| **No ORM** | Two tables, hand-written SQL, full control over upsert semantics with `ON CONFLICT DO UPDATE`. SQLAlchemy would be overkill. |
| **Pure-function planner** | `planner.py` has zero side effects → trivially unit-testable, deterministic, and reusable from the standalone `main.py` script. |
| **Dataclasses with `slots=True`** | Memory-efficient, immutable-feeling, free `__init__`/`__repr__`. |
| **Embed-based output** | Discord embeds render fixed-width code blocks reliably across desktop and mobile, which the table layouts in `formatters.py` exploit. |
| **`python-dotenv`** | Env-var configuration only — no config files, secrets stay out of the repo. |

### Quality tooling

The project enforces MAXIMUM QUALITY ENGINEERING standards (see [`CLAUDE.md`](CLAUDE.md) for the full doctrine):

- **Tests**: pytest + hypothesis, ≥90% branch coverage required.
- **Linting**: ruff (E/W/F/I/N/UP/B/C4/SIM/TCH/RUF), pylint ≥9.0.
- **Types**: mypy strict mode.
- **Formatting**: black + isort.
- **Security**: bandit + pip-audit.
- **Complexity**: radon, cyclomatic complexity ≤10 per function.

All of these run via `./scripts/check-all.sh` (Gate 1 of the Stay Green workflow). Never invoke them directly — the scripts ensure local and CI behave identically.

## Setup

### 1. Create a Discord Bot
1. Visit the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create an application → add a Bot.
3. Enable the `applications.commands` scope.
4. Generate an invite URL and invite the bot to your server.

### 2. Provision a PostgreSQL database
Anywhere you can get a connection string — Supabase, Heroku Postgres, Neon, or local `postgres`.

### 3. Configure environment
Create a `.env` file:
```
DISCORD_TOKEN=your-bot-token
PING_CHANNEL_ID=your-channel-id
DATABASE_URL=postgres://user:pass@host:5432/dbname
```

### 4. Install and run
```bash
pip install -r requirements.txt
python bot.py
```

For Heroku-style deploys the included `Procfile` runs the bot as a `worker` dyno.

## Project Structure

```
yerba-mate/
├── bot.py            # Discord client, scheduler, daily ping
├── commands.py       # Slash command cog
├── planner.py        # Pure-function reduction algorithm
├── db.py             # PostgreSQL persistence
├── formatters.py     # Discord embed builders
├── main.py           # Standalone TSV-printing script (legacy / cron)
├── requirements.txt  # Runtime deps
├── pyproject.toml    # Tooling config (mypy / ruff / pytest / coverage)
├── Procfile          # Heroku worker entrypoint
├── runtime.txt       # Python 3.12.12
├── scripts/          # check-all.sh, test.sh, lint.sh, format.sh, security.sh
├── tests/            # unit / integration / property tests
└── CLAUDE.md         # Engineering doctrine
```

## Dependencies

- [discord.py](https://github.com/Rapptz/discord.py) — Discord API wrapper with slash commands.
- [APScheduler](https://github.com/agronholm/apscheduler) — async daily ping scheduler.
- [psycopg2-binary](https://www.psycopg.org/) — PostgreSQL driver.
- [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` loader.

## License

MIT
