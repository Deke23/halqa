"""Coordinator queue membership and ordering, from engine output only."""

from __future__ import annotations

from .sla import Evaluation
from .types import CaseData, ReferralStatus, Severity, State

QUEUES = ("all", "urgent", "overdue", "rejected", "unowned", "escalated", "mine")


def is_rejected(case: CaseData) -> bool:
    return case.state is State.CONFIRMED and case.referral_status is ReferralStatus.REJECTED and case.owner_user_id is None


def in_queue(queue: str, case: CaseData, ev: Evaluation, user_id: int | None = None) -> bool:
    if queue == "all":
        return True
    if case.state is State.CLOSED:
        return False
    if queue == "urgent":
        return case.urgent
    if queue == "overdue":
        return ev.overdue
    if queue == "rejected":
        return is_rejected(case)
    if queue == "unowned":
        return case.owner_user_id is None and not is_rejected(case)
    if queue == "escalated":
        return ev.escalation_level >= 2
    if queue == "mine":
        return user_id is not None and case.owner_user_id == user_id
    raise ValueError(f"unknown queue {queue}")


def sort_key(case: CaseData, ev: Evaluation) -> tuple:
    """Urgent first (severe before red-flag), then most overdue, then soonest due."""
    due = ev.next_step.due_at.timestamp() if ev.next_step else float("inf")
    return (
        0 if case.urgent else 1,
        0 if case.severity is Severity.SEVERE else 1,
        -ev.overdue_hours,
        due,
    )
