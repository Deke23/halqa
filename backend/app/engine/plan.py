"""Lifestyle plan rules (Challenge 09 follow-up stage).

Safety property: a lapse only ever makes the plan smaller. There is no streak counter,
no reset of history and no penalty. A larger size is offered, never imposed. Three missed
check-ins in a row create a human task, not another message.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from . import config as cfg
from .types import CheckinStatus, PlanActionKey, PlanSize

SIZES: tuple[PlanSize, ...] = (PlanSize.FULL, PlanSize.SMALLER, PlanSize.SMALLEST)
ROTATION: tuple[PlanActionKey, ...] = (
    PlanActionKey.SALT,
    PlanActionKey.ACTIVITY,
    PlanActionKey.SLEEP,
    PlanActionKey.HOME_BP_CHECK,
)
BARRIERS: tuple[str, ...] = ("TIME", "COST", "NOT_SURE_HOW", "FELT_UNWELL", "WORK_SCHEDULE", "OTHER")


@dataclass(frozen=True)
class PlanWeekData:
    action_key: PlanActionKey
    size: PlanSize
    status: CheckinStatus | None  # None while the week is still open
    offered_larger: bool = False


@dataclass(frozen=True)
class PlanDecision:
    action_key: PlanActionKey
    size: PlanSize
    offer_larger: bool
    shrunk: bool
    enlarged: bool
    message_keys: tuple[str, ...]
    call_offer: bool


def first_week() -> tuple[PlanActionKey, PlanSize]:
    return ROTATION[0], PlanSize.FULL


def smaller(size: PlanSize) -> PlanSize:
    return SIZES[min(SIZES.index(size) + 1, len(SIZES) - 1)]


def larger(size: PlanSize) -> PlanSize:
    return SIZES[max(SIZES.index(size) - 1, 0)]


def _next_action(action: PlanActionKey) -> PlanActionKey:
    return ROTATION[(ROTATION.index(action) + 1) % len(ROTATION)]


def _trailing(statuses: Sequence[CheckinStatus | None], wanted: CheckinStatus) -> int:
    n = 0
    for s in reversed(statuses):
        if s != wanted:
            break
        n += 1
    return n


def decide_next(history: Sequence[PlanWeekData], accept_larger: bool = False) -> PlanDecision:
    """Plan for the next week. `history` is oldest first and ends with the week just checked in."""
    current = history[-1]
    if current.status is None:
        raise ValueError("the latest week must have a check-in status")
    statuses = [w.status for w in history]
    action, size = current.action_key, current.size
    shrunk = enlarged = offer = False
    messages: list[str] = []

    if current.status is CheckinStatus.MISSED:
        new = smaller(size)
        shrunk = new != size
        size = new
        messages.append("no_blame_checkin")
        if shrunk:
            messages.append("plan_smaller")
    elif current.status is CheckinStatus.PARTLY:
        if _trailing(statuses, CheckinStatus.PARTLY) >= int(cfg.value("lifestyle_plan", "partly_in_row_to_shrink")):
            new = smaller(size)
            shrunk = new != size
            size = new
            messages.append("no_blame_checkin")
            if shrunk:
                messages.append("plan_smaller")
    else:  # DONE
        action = _next_action(action)
        if current.offered_larger and accept_larger and larger(size) != size:
            size = larger(size)
            enlarged = True
        if _trailing(statuses, CheckinStatus.DONE) >= int(cfg.value("lifestyle_plan", "done_in_row_to_offer_larger")):
            offer = larger(size) != size
        messages.append("weekly_action")

    call = _trailing(statuses, CheckinStatus.MISSED) >= int(cfg.value("lifestyle_plan", "missed_in_row_for_call_task"))
    return PlanDecision(action, size, offer, shrunk, enlarged, tuple(messages), call)


def week_lapsed(starts_at: datetime, now: datetime) -> bool:
    """An open week with no check-in after its length plus the grace period is recorded as missed, with no blame."""
    length = timedelta(days=float(cfg.value("lifestyle_plan", "week_length")))
    grace = timedelta(days=float(cfg.value("lifestyle_plan", "lapse_grace")))
    return now > starts_at + length + grace
