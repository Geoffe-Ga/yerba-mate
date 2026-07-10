"""Plain-text formatting helpers for plan, status, and history views.

The standalone Discord bot is retired (RubotPaul is the Discord interface
now), so these builders return :class:`FormattedMessage` — pure data with
the same code-block table layouts the old embeds carried. RubotPaul (or
any other caller) decides how to render them; the Recovery Dharma tone
guidance lives in the RubotPaul-side SKILL.md, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from planner import PlanDay

# Target ~34 chars wide for mobile Discord code blocks.
# Date(5) Sm(3) Lg(3) mg(4) Drop(4) + separators = ~34
_HDR = f"{'Date':<5} {'Sm':>2} {'Lg':>2} {'mg':>4} {'Drop':>4}"
_SEP = "─" * 22

# Discord caps embed/message descriptions at 4096 characters; keep the
# tables renderable as-is even though this module no longer talks to
# Discord itself.
_BODY_LIMIT = 4096


@dataclass(slots=True, frozen=True)
class FormattedMessage:
    """A rendered view: title, body, and an optional footer line."""

    title: str
    body: str
    footer: str | None = None


def _format_drinks(small: int, large: int) -> str:
    """Format drink counts as readable text."""
    parts = []
    if small:
        parts.append(f"{small} small")
    if large:
        parts.append(f"{large} large")
    return ", ".join(parts) if parts else "none"


def _ds(d: date) -> str:
    """Short date: MM/DD."""
    return d.strftime("%m/%d")


def _row(d: date, small: int, large: int, mg: int, drop: str = "") -> str:
    """Format one row in the standard table layout."""
    return f"{_ds(d):<5} {small:>2} {large:>2} {mg:>4} {drop:>4}"


def _make_table(lines: list[str]) -> str:
    """Wrap lines in a code block."""
    return "```\n" + "\n".join(lines) + "\n```"


def plan_message(plan: list[PlanDay]) -> FormattedMessage:
    """Format the full tapering plan as a one-row-per-day table."""
    lines = [_HDR, _SEP]
    prev_mg = 0
    for p in plan:
        drop = ""
        if prev_mg and prev_mg != p.total_mg:
            diff = prev_mg - p.total_mg
            drop = f"-{diff}" if diff > 0 else f"+{-diff}"
        prev_mg = p.total_mg
        lines.append(_row(p.date, p.small, p.large, p.total_mg, drop))

    start = plan[0].date
    end = plan[-1].date
    return FormattedMessage(
        title="Yerba Mate Reduction Plan",
        body=_make_table(lines),
        footer=f"{len(plan)} days — {start} to {end}",
    )


def status_message(
    plan_day: PlanDay | None,
    actual: PlanDay | None,
    today: date,
) -> FormattedMessage:
    """Format today's status as a compact table."""
    hdr = f"{'':>6} {'Sm':>2} {'Lg':>2} {'mg':>4}"
    lines = [hdr, "─" * 17]

    if plan_day:
        lines.append(
            f"{'Plan':>6} {plan_day.small:>2} "
            f"{plan_day.large:>2} {plan_day.total_mg:>4}"
        )
    else:
        lines.append(f"{'Plan':>6}  (no plan)")

    if actual:
        lines.append(
            f"{'Actual':>6} {actual.small:>2} {actual.large:>2} {actual.total_mg:>4}"
        )
    else:
        lines.append(f"{'Actual':>6}  (not logged)")

    if plan_day and actual:
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        lines.append(f"{'Delta':>6} {'':>2} {'':>2} {sign}{delta:>3}")

    return FormattedMessage(
        title=f"Status — {today.strftime('%b %d')}",
        body=_make_table(lines),
    )


def log_confirmation_message(
    actual: PlanDay, plan_day: PlanDay | None, replaced: bool
) -> FormattedMessage:
    """Confirmation message after logging consumption."""
    title = f"Logged — {actual.date.strftime('%b %d')}"
    if replaced:
        title += " (updated)"

    hdr = f"{'':>6} {'Sm':>2} {'Lg':>2} {'mg':>4}"
    lines = [hdr, "─" * 17]
    lines.append(
        f"{'Actual':>6} {actual.small:>2} {actual.large:>2} {actual.total_mg:>4}"
    )
    if plan_day:
        lines.append(
            f"{'Plan':>6} {plan_day.small:>2} "
            f"{plan_day.large:>2} {plan_day.total_mg:>4}"
        )
        delta = actual.total_mg - plan_day.total_mg
        sign = "+" if delta > 0 else ""
        lines.append(f"{'Delta':>6} {'':>2} {'':>2} {sign}{delta:>3}")

    return FormattedMessage(title=title, body=_make_table(lines))


def history_message(
    plan_days: dict[date, PlanDay],
    actuals: dict[date, PlanDay],
    from_date: date,
    to_date: date,
) -> FormattedMessage:
    """Format history table of plan vs actual, one row per day."""
    lines = [
        f"{'Date':<5} {'Plan':>4} {'Real':>4} {'Delta':>5}",
        "─" * 21,
    ]

    d = from_date
    while d <= to_date:
        plan = plan_days.get(d)
        actual = actuals.get(d)
        p_str = str(plan.total_mg) if plan else "·"
        a_str = str(actual.total_mg) if actual else "·"
        if plan and actual:
            delta = actual.total_mg - plan.total_mg
            sign = "+" if delta > 0 else ""
            d_str = f"{sign}{delta}"
        else:
            d_str = "·"
        lines.append(f"{_ds(d):<5} {p_str:>4} {a_str:>4} {d_str:>5}")
        d += timedelta(days=1)

    table = _make_table(lines)
    if len(table) > _BODY_LIMIT:
        table = table[: _BODY_LIMIT - 3] + "```"

    return FormattedMessage(
        title=f"History — {from_date} to {to_date}",
        body=table,
    )


def daily_ping_message(plan_day: PlanDay | None, today: date) -> FormattedMessage:
    """Format the daily reminder ping."""
    if plan_day:
        drinks = _format_drinks(plan_day.small, plan_day.large)
        return FormattedMessage(
            title=f"Today's Target — {today.strftime('%b %d')}",
            body=f"**{drinks}** — **{plan_day.total_mg} mg**",
        )
    return FormattedMessage(
        title=f"No Plan for {today.strftime('%b %d')}",
        body="Use `/plan` to create a reduction plan.",
    )
