"""SQLite persistence for plan days and actual consumption."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from planner import PlanDay

DB_PATH = Path("yerba_mate.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a connection with row_factory set."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS plan_days (
            date TEXT PRIMARY KEY,
            small INTEGER NOT NULL,
            large INTEGER NOT NULL,
            total_mg INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS actuals (
            date TEXT PRIMARY KEY,
            small INTEGER NOT NULL,
            large INTEGER NOT NULL,
            total_mg INTEGER NOT NULL
        );
    """)
    conn.close()


# ---------------------------------------------------------------------------
# Plan days
# ---------------------------------------------------------------------------


def save_plan(plan: list[PlanDay], db_path: Path = DB_PATH) -> None:
    """Replace the entire plan with new days."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM plan_days")
    conn.executemany(
        "INSERT INTO plan_days (date, small, large, total_mg) VALUES (?, ?, ?, ?)",
        [(str(p.date), p.small, p.large, p.total_mg) for p in plan],
    )
    conn.commit()
    conn.close()


def replace_plan_from_date(
    plan: list[PlanDay], from_date: date, db_path: Path = DB_PATH
) -> None:
    """Delete plan days >= from_date and insert new ones."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM plan_days WHERE date >= ?", (str(from_date),))
    conn.executemany(
        "INSERT INTO plan_days (date, small, large, total_mg) VALUES (?, ?, ?, ?)",
        [(str(p.date), p.small, p.large, p.total_mg) for p in plan],
    )
    conn.commit()
    conn.close()


def get_plan_day(d: date, db_path: Path = DB_PATH) -> PlanDay | None:
    """Get the plan for a specific date."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM plan_days WHERE date = ?", (str(d),)).fetchone()
    conn.close()
    if row is None:
        return None
    return PlanDay(
        date=date.fromisoformat(row["date"]),
        small=row["small"],
        large=row["large"],
        total_mg=row["total_mg"],
    )


def get_all_plan_days(db_path: Path = DB_PATH) -> list[PlanDay]:
    """Get all plan days ordered by date."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM plan_days ORDER BY date").fetchall()
    conn.close()
    return [
        PlanDay(
            date=date.fromisoformat(r["date"]),
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]


def get_plan_days_from(from_date: date, db_path: Path = DB_PATH) -> list[PlanDay]:
    """Get plan days from a date onward."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM plan_days WHERE date >= ? ORDER BY date", (str(from_date),)
    ).fetchall()
    conn.close()
    return [
        PlanDay(
            date=date.fromisoformat(r["date"]),
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Actuals
# ---------------------------------------------------------------------------


def upsert_actual(d: date, small: int, large: int, db_path: Path = DB_PATH) -> None:
    """Insert or replace an actual consumption record."""
    total_mg = (115 * small) + (150 * large)
    conn = get_connection(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO actuals "
        "(date, small, large, total_mg) VALUES (?, ?, ?, ?)",
        (str(d), small, large, total_mg),
    )
    conn.commit()
    conn.close()


def get_actual(d: date, db_path: Path = DB_PATH) -> PlanDay | None:
    """Get actual consumption for a date (reuses PlanDay shape)."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM actuals WHERE date = ?", (str(d),)).fetchone()
    conn.close()
    if row is None:
        return None
    return PlanDay(
        date=date.fromisoformat(row["date"]),
        small=row["small"],
        large=row["large"],
        total_mg=row["total_mg"],
    )


def get_most_recent_actual(db_path: Path = DB_PATH) -> PlanDay | None:
    """Get the most recent actual entry."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM actuals ORDER BY date DESC LIMIT 1").fetchone()
    conn.close()
    if row is None:
        return None
    return PlanDay(
        date=date.fromisoformat(row["date"]),
        small=row["small"],
        large=row["large"],
        total_mg=row["total_mg"],
    )


def get_actuals_range(
    from_date: date, to_date: date, db_path: Path = DB_PATH
) -> list[PlanDay]:
    """Get actuals between two dates (inclusive)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM actuals WHERE date >= ? AND date <= ? ORDER BY date",
        (str(from_date), str(to_date)),
    ).fetchall()
    conn.close()
    return [
        PlanDay(
            date=date.fromisoformat(r["date"]),
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]


def get_plan_range(
    from_date: date, to_date: date, db_path: Path = DB_PATH
) -> list[PlanDay]:
    """Get plan days between two dates (inclusive)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM plan_days WHERE date >= ? AND date <= ? ORDER BY date",
        (str(from_date), str(to_date)),
    ).fetchall()
    conn.close()
    return [
        PlanDay(
            date=date.fromisoformat(r["date"]),
            small=r["small"],
            large=r["large"],
            total_mg=r["total_mg"],
        )
        for r in rows
    ]
