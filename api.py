"""Read-only HTTP API for RubotPaul.

Exposes the tapering plan, today's status, and consumption history over
aiohttp. Every ``/api/v1/*`` route sits behind the vendored HMAC bearer
auth (see auth_middleware.py); ``/healthz`` is unauthenticated.

DB access reuses the synchronous psycopg2 functions in db.py via
``asyncio.to_thread`` to keep churn minimal.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import TYPE_CHECKING

from aiohttp import web

import db
from auth_middleware import aiohttp_auth_middleware

if TYPE_CHECKING:
    from auth_middleware import Handler
    from planner import PlanDay

MIN_HISTORY_WEEKS = 1
MAX_HISTORY_WEEKS = 52
DEFAULT_HISTORY_WEEKS = 4


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
        return web.json_response({"error": "no plan for today"}, status=404)
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
        return web.json_response(
            {
                "error": "weeks must be an integer between "
                f"{MIN_HISTORY_WEEKS} and {MAX_HISTORY_WEEKS}"
            },
            status=400,
        )
    today = date.today()
    from_date = today - timedelta(weeks=weeks)
    plan_rows = await asyncio.to_thread(db.get_plan_range, from_date, today)
    actual_rows = await asyncio.to_thread(db.get_actuals_range, from_date, today)
    return web.json_response({"history": _merge_history(plan_rows, actual_rows)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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

    app = web.Application()
    app.router.add_get("/healthz", healthz_endpoint)
    app.add_subapp("/api/v1", api_app)
    return app
