"""Pure-function caffeine tapering plan generator.

Refactored from main.py — same reduction logic, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

SMALL_MG = 115
LARGE_MG = 150


@dataclass(slots=True)
class PlanDay:
    """A single day in the tapering schedule."""

    date: date
    small: int
    large: int
    total_mg: int


def generate_plan(small: int, large: int, start_date: date) -> list[PlanDay]:
    """Generate a caffeine tapering plan.

    Args:
        small: Starting number of small drinks per day.
        large: Starting number of large drinks per day.
        start_date: First day of the plan.

    Returns:
        Ordered list of PlanDay entries (each level held for 2 days).
    """
    caffeine = (SMALL_MG * small) + (LARGE_MG * large)
    day = start_date

    plan: list[PlanDay] = []
    i = 0

    # First level: 2 days at starting consumption
    plan.append(PlanDay(date=day, small=small, large=large, total_mg=caffeine))
    day += timedelta(days=1)
    plan.append(PlanDay(date=day, small=small, large=large, total_mg=caffeine))
    day += timedelta(days=1)
    i = 1

    while caffeine > SMALL_MG:
        if small == 2 and not large:
            large = 1
            small = 0
        elif large > 0:
            small += 1
            large -= 1
        else:
            large = small - 1
            small = 0

        new_caffeine = (SMALL_MG * small) + (LARGE_MG * large)
        last_caffeine = plan[i].total_mg

        if 0 < last_caffeine - new_caffeine < 35:
            # Step too small — replace the previous 2-day level
            day -= timedelta(days=2)
            plan[i - 1] = PlanDay(
                date=day, small=small, large=large, total_mg=new_caffeine
            )
            day += timedelta(days=1)
            plan[i] = PlanDay(date=day, small=small, large=large, total_mg=new_caffeine)
        else:
            plan.append(
                PlanDay(date=day, small=small, large=large, total_mg=new_caffeine)
            )
            day += timedelta(days=1)
            plan.append(
                PlanDay(date=day, small=small, large=large, total_mg=new_caffeine)
            )
            i += 2

        caffeine = new_caffeine
        day += timedelta(days=1)

    return plan


if __name__ == "__main__":
    # Quick verification — compare with main.py output
    for p in generate_plan(small=0, large=3, start_date=date(2025, 11, 9)):
        print(f"{p.date}\t{p.small}\t{p.large}\t{p.total_mg}")
