# Yerba Mate Reduction Service

> Step down. Don't crash.

A caffeine-tapering service for the **Conscious Biohacker** who wants to reduce caffeine intake from yerba mate **without triggering withdrawal symptoms** — the headaches, brain fog, fatigue, and irritability that come from quitting cold turkey.

It runs as a small HTTP API behind [RubotPaul](https://github.com/Geoffe-Ga) (the household OpenClaw assistant), which is the Discord-facing interface. The original standalone Discord bot is retired; see [Migration note](#migration-note-discord-bot-retired).

## Mission

Caffeine withdrawal is a real pharmacological event. The standard literature (and lived experience) shows that abrupt reductions of more than ~25% of daily intake can trigger 2–9 days of unpleasant symptoms. The *Conscious Biohacker* approach is to **taper gradually** — small, regular drops your adenosine receptors can adapt to — instead of quitting outright.

This service exists because doing that taper by hand is annoying:

1. You have to compute a step-down schedule that never drops too fast.
2. You have to remember your daily target every morning.
3. You inevitably miss a day or drink extra, and the plan needs to recover gracefully.
4. You want to look back and see whether you actually stuck to the plan.

The service automates all four. It generates a personalized tapering plan from your current intake, serves each day's target for RubotPaul's 6 AM Pacific reminder, records actual consumption (including extras, slips, and adjustments), and recalibrates the plan when life happens.

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

## API Reference

Every `/api/v1/*` route requires the RubotPaul HMAC bearer token (see
[Authentication](#authentication)); `GET /healthz` is unauthenticated.

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness probe → `{"ok": true}`. |
| `GET /api/v1/plan` | Full tapering plan with `starts_on`/`ends_on`. |
| `GET /api/v1/status` | Today's plan vs actual with `delta_mg` and `on_track` (404 if no plan for today). |
| `GET /api/v1/history?weeks=N` | Plan-vs-actual rows merged by date (default 4 weeks, max 52). |
| `POST /api/v1/log` | Record actual consumption `{large, small, date?}` — immediate write. |
| `POST /api/v1/extra` | Increment today's actuals by one `{size: "large"\|"small"}` — immediate write. |
| `POST /api/v1/plan` | **Destructive.** Stage a replan `{large, small, strategy: "replan"\|"catchup"}`; returns `action_id` + preview, writes nothing. |
| `POST /api/v1/plan/confirm` | Execute a staged replan `{action_id}` exactly once (404 unknown, 410 expired, 409 already resolved). |

Replanning follows the kit-wide **draft → confirm → execute** pattern: RubotPaul posts the preview to chat, waits for an explicit "confirm" reply, and only then calls `/plan/confirm`.

### Daily reminder

The 06:00 US/Pacific target ping now lives in **RubotPaul's scheduler**: it calls `GET /api/v1/status` and posts the result to Discord itself. This service has no scheduler of its own.

### Authentication

Requests carry `Authorization: Bearer <caller_id>.<timestamp>.<hmac_hex>`, an HMAC-SHA256 over `<caller_id>.<timestamp>` with `RUBOTPAUL_SHARED_SECRET` (300 s TTL). The middleware is vendored in `auth_middleware.py`, shared verbatim across the RubotPaul-callable services.

## Architecture

The codebase is small and deliberately split into single-purpose modules with a strict dependency graph:

```
api.py ──► auth_middleware.py  (pure)
   │
   ├──► planner.py  (pure)
   │
   ├──► db.py       ──► PostgreSQL
   │
formatters.py  (pure, RubotPaul-side rendering helpers)
```

| Module              | Responsibility                                                        | Side effects |
|---------------------|------------------------------------------------------------------------|:------------:|
| `api.py`            | aiohttp app factory, endpoints, staged-confirmation store, entrypoint  | Network, DB  |
| `auth_middleware.py`| Vendored RubotPaul HMAC bearer auth                                    | None         |
| `planner.py`        | Pure-function tapering algorithm                                       | None         |
| `db.py`             | PostgreSQL connection pool + plan/actuals persistence                  | DB           |
| `formatters.py`     | Plain-text table builders (`FormattedMessage`) for RubotPaul rendering | None         |
| `main.py`           | Original standalone TSV-printing script (kept for reference / cron use)| stdout       |

The dependency graph is acyclic: `planner` and `formatters` are pure and free of I/O, `db` knows nothing about HTTP, and `api` is the only place where domain logic, persistence, and transport meet.

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

`save_plan` / `replace_plan_from_date` always treat the plan as **append-from-cutoff**: history before the cutoff is preserved so the history view can show what *was* planned even after a replan.

## Code & Technology Choices

| Choice | Why |
|--------|-----|
| **Python 3.12** | Modern type syntax, `dataclass(slots=True)`, no FFI complications. |
| **aiohttp** | Small async HTTP server; the whole service is one event loop, no framework overhead. |
| **PostgreSQL via psycopg2** | Persistent across restarts. The `SimpleConnectionPool` keeps connection setup cheap without an ORM; handlers wrap the sync calls in `asyncio.to_thread`. |
| **No ORM** | Two tables, hand-written SQL, full control over upsert semantics with `ON CONFLICT DO UPDATE`. SQLAlchemy would be overkill. |
| **Pure-function planner** | `planner.py` has zero side effects → trivially unit-testable, deterministic, and reusable from the standalone `main.py` script. |
| **Dataclasses with `slots=True`** | Memory-efficient, immutable-feeling, free `__init__`/`__repr__`. |
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

### 1. Provision a PostgreSQL database
Anywhere you can get a connection string — Supabase, Neon, or local `postgres`. On the VPS, a local Postgres keeps everything on-box.

### 2. Configure environment
Create a `.env` file (see `.env.example`):
```
DATABASE_URL=postgres://user:pass@host:5432/dbname
RUBOTPAUL_SHARED_SECRET=shared-secret-also-known-to-rubotpaul
YERBA_API_PORT=8001
```

The entrypoint fails fast at boot, naming every missing variable, so a misconfigured unit is diagnosable from a single journal line.

### 3. Install and run
```bash
pip install -r requirements.txt
python api.py
```

The server binds `127.0.0.1:$YERBA_API_PORT` (default **8001**) — it is reachable only from the same host (RubotPaul lives there too; remote access goes over Tailscale to RubotPaul, never to this port directly).

### 4. Run as a systemd --user service (VPS deployment)

`~/.config/systemd/user/yerba-mate.service`:

```ini
[Unit]
Description=Yerba mate reduction API for RubotPaul
After=network.target

[Service]
WorkingDirectory=%h/apps/yerba-mate
EnvironmentFile=%h/apps/yerba-mate/.env
ExecStart=%h/apps/yerba-mate/.venv/bin/python api.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now yerba-mate.service
```

`SIGTERM` from `systemctl --user stop` shuts the server down gracefully (socket released, DB pool closed).

## Migration note: Discord bot retired

This repo previously shipped a standalone Discord bot (`bot.py` + a slash-command cog) with an APScheduler 6 AM ping. Per the RubotPaul migration (see the kit's `PIVOT.md`), RubotPaul is now the single Discord interface: it calls this API and renders the results in chat, and its scheduler owns the morning reminder. The **Recovery Dharma tone guidance** (warm, no shame on slip-ups, never push abstinence) lives in the RubotPaul-side `SKILL.md` — this service just serves data. `formatters.py` survives as pure table builders RubotPaul can reuse.

## Project Structure

```
yerba-mate/
├── api.py             # aiohttp endpoints + standalone entrypoint (python api.py)
├── auth_middleware.py # Vendored RubotPaul HMAC bearer auth
├── planner.py         # Pure-function reduction algorithm
├── db.py              # PostgreSQL persistence
├── formatters.py      # Plain-text table builders for RubotPaul rendering
├── main.py            # Standalone TSV-printing script (legacy / cron)
├── requirements.txt   # Runtime deps
├── pyproject.toml     # Tooling config (mypy / ruff / pytest / coverage)
├── runtime.txt        # Python 3.12.12
├── scripts/           # check-all.sh, test.sh, lint.sh, format.sh, security.sh
├── tests/             # unit / integration / property tests
└── CLAUDE.md          # Engineering doctrine
```

## Dependencies

- [aiohttp](https://github.com/aio-libs/aiohttp) — async HTTP server for the API.
- [psycopg2-binary](https://www.psycopg.org/) — PostgreSQL driver.
- [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` loader.

## License

MIT
