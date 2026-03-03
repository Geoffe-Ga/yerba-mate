"""Importable test helpers shared across test modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planner import LARGE_MG, SMALL_MG, PlanDay

if TYPE_CHECKING:
    from datetime import date


def make_plan_day(
    d: date,
    *,
    small: int = 0,
    large: int = 0,
) -> PlanDay:
    """Create a ``PlanDay`` with auto-calculated ``total_mg``."""
    return PlanDay(
        date=d,
        small=small,
        large=large,
        total_mg=(SMALL_MG * small) + (LARGE_MG * large),
    )
