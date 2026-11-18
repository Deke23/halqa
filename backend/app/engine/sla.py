"""Next step, due date, SLA flags, escalation levels and the unreachable-patient protocol.

`evaluate(case, now)` is pure. It returns only effects that have not yet been applied,
judged by the counters stored on the case, so calling it twice never repeats an effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from . import config as cfg
from .types import (
    CaseData,
    ConfirmationMethod,
    ConfirmationStatus,
    EffectKind,
    ReferralStatus,
    Role,
    Severity,
    State,
)


@dataclass(frozen=True)
class NextStep:
    label_key: str
    owner_role: Role
    acting_role: Role
    started_at: datetime
    service_level_h: float
    due_at: datetime
    urgent: bool = False


@dataclass(frozen=True)
class Effect:
    kind: EffectKind
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Evaluation:
    next_step: NextStep | None
    overdue: bool
    overdue_hours: float
    escalation_level: int
    escalation_target: str | None
    effects: tuple[Effect, ...] = ()


def _step(label: str, owner: Role, acting: Role, started: datetime, hours: float, urgent: bool = False) -> NextStep:
    return NextStep(label, owner, acting, started, hours, started + timedelta(hours=hours), urgent)


def urgent_review_pending(case: CaseData) -> bool:
    return case.urgent and not case.urgent_review_done and case.state is not State.CLOSED and case.urgent_started_at is not None


def next_step(case: CaseData) -> NextStep | None:
    """The one thing that must happen next, who is accountable, and when it is due."""
    if case.state is State.CLOSED:
        return None
    started = case.step_started_at
    sl = lambda key: cfg.hours("service_levels", key)  # noqa: E731

    if case.state is State.RESULT_ISSUED:
        key = "result_issued_severe" if case.severity is Severity.SEVERE else "result_issued"
        return _step("notify_patient", Role.COORDINATOR, Role.COORDINATOR, started, sl(key))
    if case.state is State.NOTIFIED:
        return _step("patient_acknowledge", Role.COORDINATOR, Role.PATIENT, started, sl("notified"))
    if case.state is State.ACKNOWLEDGED:
        hours = sl("acknowledged")
        if case.not_confirmed_reviewed:
            return _step("clinician_closure_decision", Role.CLINICIAN, Role.CLINICIAN, started, sl("closure_decision"))
        if case.confirmation_method is None:
            return _step("choose_confirmation_method", Role.CLINICIAN, Role.PATIENT, started, hours)
        if case.confirmation_status in (None, ConfirmationStatus.INSUFFICIENT):
            label = "attend_abpm" if case.confirmation_method is ConfirmationMethod.ABPM else "complete_home_readings"
            return _step(label, Role.CLINICIAN, Role.PATIENT, started, hours)
        return _step("clinician_review_confirmation", Role.CLINICIAN, Role.CLINICIAN, started, hours)
    if case.state is State.CONFIRMED:
        if case.referral_status is ReferralStatus.REJECTED and case.owner_user_id is None:
            return _step("reassign_or_rerefer", Role.COORDINATOR, Role.COORDINATOR, started, sl("confirmed"))
        return _step("send_referral", Role.CLINICIAN, Role.CLINICIAN, started, sl("confirmed"))
    if case.state is State.REFERRED:
        if case.referral_status is ReferralStatus.ACCEPTED:
            return _step("book_appointment", Role.COORDINATOR, Role.PATIENT, started, sl("appointment_booking"))
        return _step("accept_referral", Role.CLINICIAN, Role.CLINICIAN, started, sl("referral_accept"))
    if case.state is State.APPOINTMENT_BOOKED:
        base = case.appointment_at or started
        return _step("record_visit_outcome", Role.CLINICIAN, Role.CLINICIAN, base, sl("visit_outcome"))
    # IN_CARE
    label = "consider_closure" if case.closure_ready else "four_week_review"
    return _step(label, Role.CLINICIAN, Role.CLINICIAN, started, sl("in_care_review"))


def evaluate(case: CaseData, now: datetime) -> Evaluation:
    step = next_step(case)
    if step is None:
        return Evaluation(None, False, 0.0, 0, None)

    overdue = now > step.due_at
    overdue_hours = max(0.0, (now - step.due_at).total_seconds() / 3600) if overdue else 0.0
    mult_key = "level2_multiplier_severe" if case.severity is Severity.SEVERE else "level2_multiplier"
    level2_at = step.started_at + timedelta(hours=step.service_level_h * float(cfg.value("escalation", mult_key)))
    level = 2 if now > level2_at else (1 if overdue else 0)
    # A manual escalation stays in force until the step changes.
    level = max(level, case.escalation_level)
    target = None
    if level >= 2:
        target = "on_call_clinician" if case.severity is Severity.SEVERE else "coordinator_lead"
    elif level == 1:
        target = "owner"

    effects: list[Effect] = []
    if level >= 1 and case.escalation_level < 1:
        effects.append(Effect(EffectKind.ESCALATE_LEVEL_1, {"target": "owner", "due_at": step.due_at.isoformat()}))
    if level >= 2 and case.escalation_level < 2:
        effects.append(Effect(EffectKind.ESCALATE_LEVEL_2, {"target": target, "step": step.label_key}))

    if urgent_review_pending(case) and not case.urgent_review_escalated:
        due = case.urgent_started_at + timedelta(hours=cfg.hours("service_levels", "urgent_review"))
        if now > due:
            effects.append(Effect(EffectKind.ESCALATE_URGENT_REVIEW, {"target": "on_call_clinician", "due_at": due.isoformat()}))
    if step.acting_role is Role.PATIENT:
        effects.extend(_unreachable_effects(case, step, now))
    return Evaluation(step, overdue, overdue_hours, level, target, tuple(effects))


_PROTOCOL = (
    (EffectKind.UNREACHABLE_REMINDER, "reminder_after"),
    (EffectKind.UNREACHABLE_SECOND_CHANNEL, "second_channel_after"),
    (EffectKind.UNREACHABLE_CALL_TASK, "call_task_after"),
    (EffectKind.UNREACHABLE_CLINICIAN_DECISION, "clinician_decision_after"),
)


def _unreachable_effects(case: CaseData, step: NextStep, now: datetime) -> list[Effect]:
    elapsed_h = (now - step.started_at).total_seconds() / 3600
    out: list[Effect] = []
    for stage, (kind, key) in enumerate(_PROTOCOL, start=1):
        if stage > case.unreachable_stage and elapsed_h >= cfg.hours("unreachable_protocol", key):
            out.append(Effect(kind, {"stage": stage, "step": step.label_key}))
    return out
