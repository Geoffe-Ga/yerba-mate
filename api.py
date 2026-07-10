"""HTTP API for RubotPaul.

Exposes the tapering plan, today's status, and consumption history, plus
low-stakes write endpoints for logging drinks. Every ``/api/v1/*`` route
sits behind the vendored HMAC bearer auth (see auth_middleware.py);
``/healthz`` is unauthenticated. Low-stakes writes execute immediately
with no confirmation step, per the kit's safety model.

DB access reuses the synchronous psycopg2 functions in db.py via
``asyncio.to_thread`` to keep churn minimal.

Destructive operations (replanning) follow the draft→confirm→execute
pattern: ``POST /api/v1/plan`` only stages a pending action and returns a
preview; nothing is written until ``POST /api/v1/plan/confirm`` receives
the action_id, which RubotPaul sends only after an explicit "confirm"
reply in chat (see PIVOT.md). The pending store is an in-memory dict on
the app — fine for the single-host VPS deployment.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from aiohttp import web

import db
from auth_middleware import aiohttp_auth_middleware
from planner import LARGE_MG, SMALL_MG, generate_plan

if TYPE_CHECKING:
    from auth_middleware import Handler
    from planner import PlanDay

MIN_HISTORY_WEEKS = 1
MAX_HISTORY_WEEKS = 52
DEFAULT_HISTORY_WEEKS = 4

PLAN_TTL_SECONDS = 300
PLAN_STRATEGIES = ("replan", "catchup")


@dataclass(slots=True)
class PendingAction:
    """A staged destructive action awaiting chat confirmation."""

    kind: str
    payload: dict[str, int | str]
    expires_at: datetime
    status: str = "pending"
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))


PENDING_ACTIONS_KEY: web.AppKey[dict[str, PendingAction]] = web.AppKey(
    "pending_actions", dict
)


@web.middleware
async def _auth_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    """Adapt the vendored old-style middleware factory to aiohttp's new style.

    Args:
        request: The incoming HTTP request.
        handler: The downstream route handler.

    Returns:
        The wrapped handler's response, or a 401 on auth failure.
    """
    wrapped = await aiohttp_auth_middleware(request.app, handler)
    return await wrapped(request)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def healthz_endpoint(request: web.Request) -> web.Response:
    """Report process liveness. Unauthenticated by design."""
    return web.json_response({"ok": True})


async def get_plan_endpoint(request: web.Request) -> web.Response:
    """Return the full tapering plan with its date bounds."""
    rows = await asyncio.to_thread(db.get_all_plan_days)
    return web.json_response(
        {
            "plan": [_serialize(row) for row in rows],
            "starts_on": rows[0].date.isoformat() if rows else None,
            "ends_on": rows[-1].date.isoformat() if rows else None,
        }
    )


async def get_status_endpoint(request: web.Request) -> web.Response:
    """Return today's planned vs actual consumption."""
    today = date.today()
    plan = await asyncio.to_thread(db.get_plan_day, today)
    if plan is None:
        return _error_response("no plan for today", status=404)
    actual = _counts(await asyncio.to_thread(db.get_actual, today))
    return web.json_response(
        {
            "date": today.isoformat(),
            "plan": _counts(plan),
            "actual": actual,
            "delta_mg": actual["total_mg"] - plan.total_mg,
            "on_track": actual["total_mg"] <= plan.total_mg,
        }
    )


async def get_history_endpoint(request: web.Request) -> web.Response:
    """Return planned vs actual rows for the past ``?weeks=N`` weeks."""
    weeks = _parse_weeks(request.query.get("weeks", str(DEFAULT_HISTORY_WEEKS)))
    if weeks is None:
        return _error_response(
            "weeks must be an integer between "
            f"{MIN_HISTORY_WEEKS} and {MAX_HISTORY_WEEKS}"
        )
    today = date.today()
    from_date = today - timedelta(weeks=weeks)
    plan_rows = await asyncio.to_thread(db.get_plan_range, from_date, today)
    actual_rows = await asyncio.to_thread(db.get_actuals_range, from_date, today)
    return web.json_response({"history": _merge_history(plan_rows, actual_rows)})


async def post_log_endpoint(request: web.Request) -> web.Response:
    """Log a day's consumption immediately (low-stakes write, no confirmation)."""
    body = await _read_json_object(request)
    if body is None:
        return _error_response("request body must be a JSON object")
    small = _parse_count(body.get("small", 0))
    large = _parse_count(body.get("large", 0))
    if small is None or large is None:
        return _error_response("large and small must be non-negative integers")
    log_date = _parse_log_date(body.get("date", "today"))
    if log_date is None:
        return _error_response('date must be "today" or an ISO date (YYYY-MM-DD)')
    await asyncio.to_thread(db.upsert_actual, log_date, small, large)
    return _logged_response(log_date, small, large)


async def post_extra_endpoint(request: web.Request) -> web.Response:
    """Add one extra drink to today's actuals (low-stakes write)."""
    body = await _read_json_object(request)
    if body is None:
        return _error_response("request body must be a JSON object")
    size = body.get("size")
    if size not in ("large", "small"):
        return _error_response("size must be 'large' or 'small'")
    today = date.today()
    current = _counts(await asyncio.to_thread(db.get_actual, today))
    small = current["small"] + (1 if size == "small" else 0)
    large = current["large"] + (1 if size == "large" else 0)
    await asyncio.to_thread(db.upsert_actual, today, small, large)
    return _logged_response(today, small, large)


async def post_plan_endpoint(request: web.Request) -> web.Response:
    """Stage a plan replacement for confirmation. Writes nothing.

    Returns a pending action_id plus a preview of the plan that
    ``/plan/confirm`` would write, so RubotPaul can post a draft in chat.
    """
    body = await _read_json_object(request)
    if body is None:
        return _error_response("request body must be a JSON object")
    small = _parse_count(body.get("small", 0))
    large = _parse_count(body.get("large", 0))
    if small is None or large is None:
        return _error_response("large and small must be non-negative integers")
    strategy = body.get("strategy", "replan")
    if strategy not in PLAN_STRATEGIES:
        return _error_response("strategy must be 'replan' or 'catchup'")
    action = PendingAction(
        kind="plan_create",
        payload={"large": large, "small": small, "strategy": strategy},
        expires_at=_utcnow() + timedelta(seconds=PLAN_TTL_SECONDS),
    )
    request.app[PENDING_ACTIONS_KEY][action.action_id] = action
    preview = _staged_plan(small=small, large=large, strategy=strategy)
    return web.json_response(
        {
            "status": "pending_confirmation",
            "action_id": action.action_id,
            "kind": action.kind,
            "expires_in": PLAN_TTL_SECONDS,
            "preview": {
                "large": large,
                "small": small,
                "strategy": strategy,
                "days": len(preview),
                "starts_on": preview[0].date.isoformat() if preview else None,
                "ends_on": preview[-1].date.isoformat() if preview else None,
            },
        }
    )


async def post_plan_confirm_endpoint(request: web.Request) -> web.Response:
    """Execute a staged plan replacement after chat confirmation."""
    body = await _read_json_object(request)
    if body is None:
        return _error_response("request body must be a JSON object")
    action_id = body.get("action_id")
    if not isinstance(action_id, str) or not action_id:
        return _error_response("action_id must be a string")
    action = request.app[PENDING_ACTIONS_KEY].get(action_id)
    if action is None:
        return _error_response("unknown action_id", status=404)
    if action.status != "pending":
        return _error_response("action already resolved", status=409)
    if _utcnow() > action.expires_at:
        action.status = "expired"
        return _error_response("action expired", status=410)
    plan = _staged_plan(
        small=int(action.payload["small"]),
        large=int(action.payload["large"]),
        strategy=str(action.payload["strategy"]),
    )
    await asyncio.to_thread(db.save_plan, plan)
    action.status = "approved"
    return web.json_response(
        {
            "status": "executed",
            "action_id": action.action_id,
            "kind": action.kind,
            "plan": {
                "days": len(plan),
                "starts_on": plan[0].date.isoformat() if plan else None,
                "ends_on": plan[-1].date.isoformat() if plan else None,
            },
        }
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current UTC time (separate for test injection)."""
    return datetime.now(tz=UTC)


def _staged_plan(*, small: int, large: int, strategy: str) -> list[PlanDay]:
    """Build the plan a staged action would write.

    ``replan`` restarts from today with the standard 2-day hold (like the
    bot's /plan command); ``catchup`` starts tomorrow at the given level
    and reduces immediately, preserving today's plan (like /adjust).
    ``db.save_plan`` uses the first day as its deletion boundary, so the
    start date also controls how much of the old plan survives.
    """
    if strategy == "replan":
        return generate_plan(small=small, large=large, start_date=date.today())
    return generate_plan(
        small=small,
        large=large,
        start_date=date.today() + timedelta(days=1),
        skip_hold=True,
    )


def _error_response(message: str, status: int = 400) -> web.Response:
    """Build a JSON error body with the given status."""
    return web.json_response({"error": message}, status=status)


async def _read_json_object(request: web.Request) -> dict[str, object] | None:
    """Read the request body as a JSON object, returning None when invalid."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return None
    return body if isinstance(body, dict) else None


def _parse_count(value: object) -> int | None:
    """Validate a drink count: a non-negative int (bools excluded), else None."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _parse_log_date(raw: object) -> date | None:
    """Resolve a log date: "today" or an ISO date string, else None."""
    if raw == "today":
        return date.today()
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _logged_response(d: date, small: int, large: int) -> web.Response:
    """Serialize the state just written for a log/extra response."""
    return web.json_response(
        {
            "date": d.isoformat(),
            "small": small,
            "large": large,
            "total_mg": (SMALL_MG * small) + (LARGE_MG * large),
        }
    )


def _parse_weeks(raw: str) -> int | None:
    """Parse the ``weeks`` query parameter, returning None when invalid."""
    try:
        weeks = int(raw)
    except ValueError:
        return None
    if weeks < MIN_HISTORY_WEEKS or weeks > MAX_HISTORY_WEEKS:
        return None
    return weeks


def _counts(day: PlanDay | None) -> dict[str, int]:
    """Extract drink counts from a row, defaulting to zeros for None."""
    if day is None:
        return {"small": 0, "large": 0, "total_mg": 0}
    return {"small": day.small, "large": day.large, "total_mg": day.total_mg}


def _serialize(day: PlanDay) -> dict[str, object]:
    """Serialize a plan/actual row with its date as an ISO string."""
    return {"date": day.date.isoformat(), **_counts(day)}


def _merge_history(
    plan_rows: list[PlanDay], actual_rows: list[PlanDay]
) -> list[dict[str, object]]:
    """Join plan and actual rows on date, sorted ascending.

    Dates present on only one side get None for the missing side, matching
    the /history Discord command's plan-vs-actual view.
    """
    plan_map = {row.date: row for row in plan_rows}
    actual_map = {row.date: row for row in actual_rows}
    return [
        {
            "date": d.isoformat(),
            "plan": _counts(plan_map[d]) if d in plan_map else None,
            "actual": _counts(actual_map[d]) if d in actual_map else None,
        }
        for d in sorted(set(plan_map) | set(actual_map))
    ]


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def build_app() -> web.Application:
    """Create the aiohttp application with /api/v1 behind bearer auth."""
    api_app = web.Application(middlewares=[_auth_middleware])
    api_app.router.add_get("/plan", get_plan_endpoint)
    api_app.router.add_get("/status", get_status_endpoint)
    api_app.router.add_get("/history", get_history_endpoint)
    api_app.router.add_post("/log", post_log_endpoint)
    api_app.router.add_post("/extra", post_extra_endpoint)
    api_app.router.add_post("/plan", post_plan_endpoint)
    api_app.router.add_post("/plan/confirm", post_plan_confirm_endpoint)
    api_app[PENDING_ACTIONS_KEY] = {}

    app = web.Application()
    app.router.add_get("/healthz", healthz_endpoint)
    app.add_subapp("/api/v1", api_app)
    return app
