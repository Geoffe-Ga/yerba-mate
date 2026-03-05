"""PostgreSQL persistence for plan days and actual consumption."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

from planner import PlanDay

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import date

    import psycopg2

_pool: SimpleConnectionPool | None = None


def init_db(database_url: str | None = None) -> None:
    """Create the connection pool and tables.

    Args:
        database_url: PostgreSQL DSN.  Falls back to the ``DATABASE_URL``
            environment variable when *None*.
    """
    global _pool
    dsn = database_url or os.environ["DATABASE_URL"]
    _pool = SimpleConnectionPool(1, 10, dsn)

    with _connection() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plan_days (
                date DATE PRIMARY KEY,
                small INTEGER NOT NULL,
                large INTEGER NOT NULL,
                total_mg INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS actuals (
                date DATE PRIMARY KEY,
                small INTEGER NOT NULL,
                large INTEGER NOT NULL,
                total_mg INTEGER NOT NULL
            )
        """)
        conn.commit()


def close_db() -> None:
    """Close the connection pool (useful for tests)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def _connection() -> Iterator[psycopg2.extensions.connection]:
    """Get a connection from the pool, returning it on exit."""
    assert _pool is not None, "Call init_db() before using the database"
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


# ---------------------------------------------------------------------------
# Plan days
# ---------------------------------------------------------------------------


def save_plan(plan: list[PlanDay]) -> None:
    """Save a plan, preserving historical plan days before the start date.

    The plan must be sorted by date ascending — ``plan[0].date`` is used
    as the deletion boundary.
    """
    if not plan:
        return
    start = plan[0].date
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM plan_days WHERE date >= %s", (start,))
        for p in plan:
            cur.execute(
                "INSERT INTO plan_days (date, small, large, total_mg) "
                "VALUES (%s, %s, %s, %s)",
                (p.date, p.small, p.large, p.total_mg),
            )
        conn.commit()


def replace_plan_from_date(plan: list[PlanDay], from_date: date) -> None:
    """Delete plan days >= from_date and insert new ones."""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM plan_days WHERE date >= %s", (from_date,))
        for p in plan:
            cur.execute(
                "INSERT INTO plan_days (date, small, large, total_mg) "
                "VALUES (%s, %s, %s, %s)",
                (p.date, p.small, p.large, p.total_mg),
            )
        conn.commit()


def get_plan_day(d: date) -> PlanDay | None:
    """Get the plan for a specific date."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM plan_days WHERE date = %s", (d,))
        row = cur.fetchone()
    if row is None:
        return None
    return PlanDay(
        date=row["date"],
        small=row["small"],
        large=row["large"],
        total_mg=row["total_mg"],
    )


def get_all_plan_days() -> list[PlanDay]:
    """Get all plan days ordered by date."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM plan_days ORDER BY date")
        rows = cur.fetchall()
    return [
        PlanDay(
            date=r["date"],
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]


def get_plan_days_from(from_date: date) -> list[PlanDay]:
    """Get plan days from a date onward."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM plan_days WHERE date >= %s ORDER BY date",
            (from_date,),
        )
        rows = cur.fetchall()
    return [
        PlanDay(
            date=r["date"],
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Actuals
# ---------------------------------------------------------------------------


def upsert_actual(d: date, small: int, large: int) -> None:
    """Insert or update an actual consumption record."""
    total_mg = (115 * small) + (150 * large)
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO actuals (date, small, large, total_mg) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (date) DO UPDATE SET "
            "small = EXCLUDED.small, large = EXCLUDED.large, "
            "total_mg = EXCLUDED.total_mg",
            (d, small, large, total_mg),
        )
        conn.commit()


def get_actual(d: date) -> PlanDay | None:
    """Get actual consumption for a date (reuses PlanDay shape)."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM actuals WHERE date = %s", (d,))
        row = cur.fetchone()
    if row is None:
        return None
    return PlanDay(
        date=row["date"],
        small=row["small"],
        large=row["large"],
        total_mg=row["total_mg"],
    )


def get_most_recent_actual() -> PlanDay | None:
    """Get the most recent actual entry."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM actuals ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
    if row is None:
        return None
    return PlanDay(
        date=row["date"],
        small=row["small"],
        large=row["large"],
        total_mg=row["total_mg"],
    )


def get_actuals_range(from_date: date, to_date: date) -> list[PlanDay]:
    """Get actuals between two dates (inclusive)."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM actuals WHERE date >= %s AND date <= %s ORDER BY date",
            (from_date, to_date),
        )
        rows = cur.fetchall()
    return [
        PlanDay(
            date=r["date"],
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]


def get_plan_range(from_date: date, to_date: date) -> list[PlanDay]:
    """Get plan days between two dates (inclusive)."""
    with _connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM plan_days WHERE date >= %s AND date <= %s ORDER BY date",
            (from_date, to_date),
        )
        rows = cur.fetchall()
    return [
        PlanDay(
            date=r["date"],
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]
