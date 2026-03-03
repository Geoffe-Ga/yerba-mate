"""Tests for db.save_plan history-preservation behaviour (PR #7)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is importable
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import db  # noqa: E402
from planner import LARGE_MG, SMALL_MG, PlanDay  # noqa: E402


def _plan_day(d: date, *, small: int = 0, large: int = 0) -> PlanDay:
    """Create a PlanDay with auto-calculated total_mg."""
    return PlanDay(
        date=d,
        small=small,
        large=large,
        total_mg=(SMALL_MG * small) + (LARGE_MG * large),
    )


def test_save_plan_preserves_past_plan_days(tmp_db: Path) -> None:
    """Saving a new plan keeps plan days that precede the new start date."""
    old_day = _plan_day(date(2025, 1, 1), small=2, large=1)
    db.save_plan([old_day], db_path=tmp_db)

    new_day = _plan_day(date(2025, 2, 1), small=1, large=1)
    db.save_plan([new_day], db_path=tmp_db)

    all_days = db.get_all_plan_days(db_path=tmp_db)
    dates = [d.date for d in all_days]
    assert date(2025, 1, 1) in dates
    assert date(2025, 2, 1) in dates
    assert len(all_days) == 2


def test_save_plan_replaces_from_start_date_onward(tmp_db: Path) -> None:
    """New plan replaces days from its start date, keeps earlier days."""
    base = date(2025, 3, 1)
    original = [_plan_day(base + timedelta(days=i), small=3, large=0) for i in range(5)]
    db.save_plan(original, db_path=tmp_db)

    # Overlapping plan starting on day 3
    overlap_start = base + timedelta(days=2)
    replacement = [
        _plan_day(overlap_start + timedelta(days=i), small=1, large=0) for i in range(3)
    ]
    db.save_plan(replacement, db_path=tmp_db)

    all_days = db.get_all_plan_days(db_path=tmp_db)
    assert len(all_days) == 5  # 2 preserved + 3 replaced

    # First two days still have original values
    assert all_days[0].small == 3
    assert all_days[1].small == 3
    # Remaining days have replacement values
    for d in all_days[2:]:
        assert d.small == 1


def test_save_plan_empty_is_noop(tmp_db: Path) -> None:
    """Saving an empty plan does not delete existing data."""
    day = _plan_day(date(2025, 4, 1), small=2, large=2)
    db.save_plan([day], db_path=tmp_db)

    db.save_plan([], db_path=tmp_db)

    all_days = db.get_all_plan_days(db_path=tmp_db)
    assert len(all_days) == 1
    assert all_days[0].date == date(2025, 4, 1)


def test_history_survives_replanning(tmp_db: Path) -> None:
    """Mid-week replan preserves completed days, replaces future ones."""
    monday = date(2025, 5, 5)
    week = [
        _plan_day(monday + timedelta(days=i), small=4 - i, large=1) for i in range(7)
    ]
    db.save_plan(week, db_path=tmp_db)

    # Replan starting Wednesday (day index 2)
    wednesday = monday + timedelta(days=2)
    new_plan = [
        _plan_day(wednesday + timedelta(days=i), small=0, large=2) for i in range(5)
    ]
    db.save_plan(new_plan, db_path=tmp_db)

    all_days = db.get_all_plan_days(db_path=tmp_db)

    # Mon + Tue preserved, Wed-Sun replaced
    assert all_days[0].date == monday
    assert all_days[0].small == 4
    assert all_days[1].date == monday + timedelta(days=1)
    assert all_days[1].small == 3

    # Wednesday onward has new plan values
    for d in all_days[2:]:
        assert d.small == 0
        assert d.large == 2
