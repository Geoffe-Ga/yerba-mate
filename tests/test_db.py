"""Tests for db.save_plan history-preservation behaviour (PR #7)."""

from __future__ import annotations

from datetime import date, timedelta

from helpers import make_plan_day

import db


def test_save_plan_preserves_past_plan_days(tmp_db: None) -> None:
    """Saving a new plan keeps plan days that precede the new start date."""
    old_day = make_plan_day(date(2025, 1, 1), small=2, large=1)
    db.save_plan([old_day])

    new_day = make_plan_day(date(2025, 2, 1), small=1, large=1)
    db.save_plan([new_day])

    all_days = db.get_all_plan_days()
    dates = [d.date for d in all_days]
    assert date(2025, 1, 1) in dates
    assert date(2025, 2, 1) in dates
    assert len(all_days) == 2


def test_save_plan_replaces_from_start_date_onward(tmp_db: None) -> None:
    """New plan replaces days from its start date, keeps earlier days."""
    base = date(2025, 3, 1)
    original = [
        make_plan_day(base + timedelta(days=i), small=3, large=0) for i in range(5)
    ]
    db.save_plan(original)

    overlap_start = base + timedelta(days=2)
    replacement = [
        make_plan_day(overlap_start + timedelta(days=i), small=1, large=0)
        for i in range(3)
    ]
    db.save_plan(replacement)

    all_days = db.get_all_plan_days()
    assert len(all_days) == 5  # 2 preserved + 3 replaced

    assert all_days[0].small == 3
    assert all_days[1].small == 3
    for d in all_days[2:]:
        assert d.small == 1


def test_save_plan_empty_is_noop(tmp_db: None) -> None:
    """Saving an empty plan does not delete existing data."""
    day = make_plan_day(date(2025, 4, 1), small=2, large=2)
    db.save_plan([day])

    db.save_plan([])

    all_days = db.get_all_plan_days()
    assert len(all_days) == 1
    assert all_days[0].date == date(2025, 4, 1)


def test_history_survives_replanning(tmp_db: None) -> None:
    """Mid-week replan preserves completed days, replaces future ones."""
    monday = date(2025, 5, 5)
    week = [
        make_plan_day(monday + timedelta(days=i), small=4 - i, large=1)
        for i in range(7)
    ]
    db.save_plan(week)

    wednesday = monday + timedelta(days=2)
    new_plan = [
        make_plan_day(wednesday + timedelta(days=i), small=0, large=2) for i in range(5)
    ]
    db.save_plan(new_plan)

    all_days = db.get_all_plan_days()

    assert all_days[0].date == monday
    assert all_days[0].small == 4
    assert all_days[1].date == monday + timedelta(days=1)
    assert all_days[1].small == 3

    for d in all_days[2:]:
        assert d.small == 0
        assert d.large == 2
