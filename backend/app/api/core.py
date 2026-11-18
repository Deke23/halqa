"""Shared case helpers: snapshots for the engine, event log, owners, messages, tick.

This module is the bridge between rows and the pure engine. Every decision is the engine's;
this code only reads rows into a `CaseData`, then writes what the engine returned.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import (
    Appointment, Case, CaseEvent, Consent, EConsult, Message, Patient, PlanWeek, Reading, Referral, Task, User,
)
from app.engine import plan as plan_rules
from app.engine.types import (
    CaseData, CheckinStatus, ConfirmationMethod, ConfirmationStatus, EffectKind, EventType, PlanActionKey,
    PlanSize, ReadingData, ReadingSource, ReferralStatus, Role, Severity, State, STATE_ORDER,
)

from . import wording_port
from .regions import emergency_text


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


# ------------------------------------------------------------------ lookups


def user_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    return u.name if u else None


def readings_of(db: Session, case_id: int) -> list[Reading]:
    return list(db.scalars(select(Reading).where(Reading.case_id == case_id).order_by(Reading.taken_at, Reading.id)))


def reading_data(rows: list[Reading]) -> list[ReadingData]:
    return [ReadingData(r.systolic, r.diastolic, r.taken_at, ReadingSource(r.source)) for r in rows]


def referrals_of(db: Session, case_id: int) -> list[Referral]:
    return list(db.scalars(select(Referral).where(Referral.case_id == case_id).order_by(Referral.id)))


def latest_referral(db: Session, case_id: int) -> Referral | None:
    rows = referrals_of(db, case_id)
    return rows[-1] if rows else None


def appointment_of(db: Session, case_id: int) -> Appointment | None:
    return db.scalars(select(Appointment).where(Appointment.case_id == case_id).order_by(Appointment.id.desc())).first()


def consent_granted(db: Session, patient_id: int, purpose: str, channel: str | None = None) -> bool:
    """True unless a matching consent record exists and is currently withdrawn."""
    q = select(Consent).where(Consent.patient_id == patient_id, Consent.purpose == purpose)
    if channel:
        q = q.where(Consent.channel == channel)
    rows = list(db.scalars(q))
    return all(c.granted for c in rows) if rows else True


def plan_weeks(db: Session, case_id: int) -> list[PlanWeek]:
    return list(db.scalars(select(PlanWeek).where(PlanWeek.case_id == case_id).order_by(PlanWeek.week_index)))


def open_week(db: Session, case_id: int) -> PlanWeek | None:
    weeks = [w for w in plan_weeks(db, case_id) if w.status is None]
    return weeks[-1] if weeks else None


def open_task(db: Session, case_id: int, task_type: str) -> Task | None:
    return db.scalars(select(Task).where(Task.case_id == case_id, Task.type == task_type, Task.status == "OPEN")).first()


# ------------------------------------------------------------------ engine snapshot


def case_data(db: Session, case: Case, readings: list[Reading] | None = None) -> CaseData:
    rows = readings if readings is not None else readings_of(db, case.id)
    rdata = reading_data(rows)
    method = ConfirmationMethod(case.confirmation_method) if case.confirmation_method else None
    conf = engine.evaluate_confirmation(method, rdata)
    ref = latest_referral(db, case.id)
    appt = appointment_of(db, case.id) if case.state == State.APPOINTMENT_BOOKED.value else None
    return CaseData(
        state=State(case.state),
        severity=Severity(case.severity),
        urgent=case.urgent,
        urgent_started_at=case.urgent_started_at,
        urgent_review_done=case.urgent_review_done_at is not None,
        urgent_review_escalated=case.urgent_review_escalated,
        step_started_at=case.step_started_at,
        owner_user_id=case.owner_user_id,
        referral_status=ReferralStatus(case.referral_status) if case.referral_status else None,
        referral_to_user_id=ref.to_user_id if ref else None,
        appointment_at=appt.starts_at if appt else None,
        confirmation_method=method,
        confirmation_status=conf.status if conf else None,
        not_confirmed_reviewed=case.suggested_closure_type == "NOT_CONFIRMED" and case.state == State.ACKNOWLEDGED.value,
        closure_ready=case.state == State.IN_CARE.value and engine.urgency.at_target(rdata),
        share_consent_granted=consent_granted(db, case.patient_id, "share_with_receiving_provider"),
        escalation_level=case.escalation_level,
        unreachable_stage=case.unreachable_stage,
        needs_clinician_decision=case.needs_clinician_decision,
    )


# ------------------------------------------------------------------ events


def log(
    db: Session, case: Case, now: datetime, type_: EventType, actor: User | None = None, *,
    from_state: str | None = None, to_state: str | None = None, payload: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    db.add(CaseEvent(
        case_id=case.id, at=now, actor_user_id=actor.id if actor else None,
        actor=str(actor.id) if actor else "system", actor_role=actor.role if actor else "system",
        type=type_.value, from_state=from_state, to_state=to_state, payload=payload or {}, reason=reason,
    ))


def add_task(
    db: Session, case: Case, now: datetime, task_type: str, title_key: str, owner_role: str,
    owner_user_id: int | None = None, due_at: datetime | None = None, payload: dict[str, Any] | None = None,
) -> Task:
    task = Task(case_id=case.id, type=task_type, title_key=title_key, owner_role=owner_role,
                owner_user_id=owner_user_id, due_at=due_at, created_at=now, payload=payload or {})
    db.add(task)
    log(db, case, now, EventType.TASK_CREATED, payload={"task_type": task_type, "owner_role": owner_role})
    return task


def complete_tasks(db: Session, case_id: int, task_type: str, now: datetime) -> None:
    for t in db.scalars(select(Task).where(Task.case_id == case_id, Task.type == task_type, Task.status == "OPEN")):
        t.status, t.completed_at = "DONE", now


# ------------------------------------------------------------------ owners and steps


def _active(db: Session, user_id: int | None) -> int | None:
    u = db.get(User, user_id) if user_id else None
    return u.id if u and u.active else None


def default_owner(db: Session, case: Case, role: Role) -> int | None:
    if role is Role.COORDINATOR:
        q = select(User).where(User.role == "coordinator", User.region == case.region, User.active.is_(True)).order_by(User.id)
        u = db.scalars(q).first()
        return u.id if u else None
    patient = db.get(Patient, case.patient_id)
    ref = latest_referral(db, case.id)
    if case.state in (State.REFERRED.value, State.APPOINTMENT_BOOKED.value, State.IN_CARE.value) and ref and ref.to_user_id:
        return _active(db, ref.to_user_id)
    return _active(db, patient.primary_clinician_id if patient else None)


def sync_owner(db: Session, case: Case) -> None:
    db.flush()
    step = engine.next_step(case_data(db, case))
    if step is None:
        return
    case.owner_role = step.owner_role.value
    case.owner_user_id = default_owner(db, case, step.owner_role)


def begin_step(db: Session, case: Case, now: datetime, *, sync: bool = True) -> None:
    """A new step starts: restart the clock, reset escalation counters, assign the default owner."""
    case.step_started_at = now
    case.escalation_level = 0
    case.unreachable_stage = 0
    case.needs_clinician_decision = False
    if sync:
        sync_owner(db, case)


def set_state(db: Session, case: Case, to: State, now: datetime) -> str:
    before = case.state
    case.state = to.value
    ms = dict(case.milestones or {})
    # A step back (rejected referral, reopen) keeps the time the earlier milestone was first reached.
    if to.value not in ms or STATE_ORDER.index(to) > STATE_ORDER.index(State(before)):
        ms[to.value] = now.isoformat()
    case.milestones = ms
    return before


def flag_urgent(db: Session, case: Case, now: datetime, reason: str, actor: User | None = None) -> bool:
    """Mark urgent and create the parallel urgent_review task for the clinician role. Idempotent while pending."""
    if case.urgent and case.urgent_review_done_at is None:
        return False
    hours = engine.config.hours("service_levels", "urgent_review")
    case.urgent, case.urgent_reason = True, reason
    case.urgent_started_at, case.urgent_review_done_at, case.urgent_review_escalated = now, None, False
    due = now + timedelta(hours=hours)
    db.flush()
    patient = db.get(Patient, case.patient_id)
    add_task(db, case, now, "URGENT_REVIEW", "urgent_review", "clinician",
             _active(db, patient.primary_clinician_id if patient else None), due, {"reason": reason})
    log(db, case, now, EventType.URGENT_FLAGGED, actor, payload={"reason": reason, "due_at": due.isoformat()})
    return True


# ------------------------------------------------------------------ messages


def first_name(patient: Patient) -> str:
    return patient.display_name.split()[0]


def slots_for(db: Session, case: Case, extra: dict[str, Any] | None = None, language: str | None = None) -> dict[str, Any]:
    patient = db.get(Patient, case.patient_id)
    rows = readings_of(db, case.id)
    last = rows[-1] if rows else None
    s, d = (last.systolic, last.diastolic) if last else (case.index_systolic, case.index_diastolic)
    lang = language or patient.language
    step = engine.next_step(case_data(db, case))
    due = step.due_at if step else None
    slots: dict[str, Any] = {
        "name": first_name(patient), "patient_name": first_name(patient),
        "systolic": s, "diastolic": d, "reading": f"{s}/{d}",
        "phone": patient.phone or "", "clinic": patient.organisation, "clinic_name": patient.organisation, "provider": "",
        "date": "", "time": "", "appointment_date": "", "appointment_time": "", "action": "", "action_text": "", "closure_reason": "",
        "due_date": wording_port.format_date(due, lang) if due else "",
        "review_time": (case.urgent_started_at + timedelta(hours=engine.config.hours("service_levels", "urgent_review"))).strftime("%H:%M")
        if case.urgent_started_at else "",
        "emergency_instruction": emergency_text(case.region, lang),
        "closed_date": wording_port.format_date(case.closed_at, lang) if case.closed_at else "",
    }
    appt = appointment_of(db, case.id)
    if appt:
        slots.update(date=appt.starts_at.strftime("%Y-%m-%d"), time=appt.starts_at.strftime("%H:%M"),
                     appointment_date=wording_port.format_date(appt.starts_at, lang), appointment_time=appt.starts_at.strftime("%H:%M"),
                     clinic=appt.location, clinic_name=appt.location, provider=appt.provider_name)
    slots.update(extra or {})
    return slots


def add_message(
    db: Session, case: Case, now: datetime, template_id: str | None, text: str, *, language: str, channel: str,
    direction: str = "OUT", sender: User | None = None, source: str = "TEMPLATE", version: str | None = None,
    approved_by: User | None = None,
) -> Message:
    msg = Message(
        case_id=case.id, direction=direction, channel=channel, language=language, text=text, template_id=template_id,
        template_version=version, source=source, sender_user_id=sender.id if sender else None,
        approved_by_user_id=approved_by.id if approved_by else None, created_at=now,
    )
    db.add(msg)
    return msg


def send_template(
    db: Session, case: Case, now: datetime, template_id: str, *, sender: User | None = None,
    language: str | None = None, channel: str | None = None, extra: dict[str, Any] | None = None,
) -> Message:
    patient = db.get(Patient, case.patient_id)
    lang = language or patient.language
    chan = channel or patient.channel
    out = wording_port.render(template_id, lang, slots_for(db, case, extra), chan)
    msg = add_message(db, case, now, template_id, out.text, language=lang, channel=chan,
                      sender=sender, version=out.template_version)
    log(db, case, now, EventType.MESSAGE_SENT, sender,
        payload={"template_id": template_id, "channel": msg.channel, "language": lang, "source": "TEMPLATE"})
    return msg


# ------------------------------------------------------------------ lifestyle plan


def start_plan(db: Session, case: Case, now: datetime) -> None:
    if not consent_granted(db, case.patient_id, "lifestyle_programme"):
        return
    action, size = plan_rules.first_week()
    db.add(PlanWeek(case_id=case.id, week_index=1, action_key=action.value, size=size.value, starts_at=now))


def record_checkin(
    db: Session, case: Case, week: PlanWeek, status: CheckinStatus, now: datetime, *, barrier: str | None = None,
    accept_larger: bool = False, actor: User | None = None, auto: bool = False,
) -> dict[str, Any]:
    """Close the open week and create the next one. Returns what the patient should be told."""
    week.status, week.barrier, week.checked_in_at, week.auto_recorded = status.value, barrier, now, auto
    db.flush()
    history = [
        plan_rules.PlanWeekData(PlanActionKey(w.action_key), PlanSize(w.size), CheckinStatus(w.status) if w.status else None, w.offered_larger)
        for w in plan_weeks(db, case.id) if w.status is not None
    ]
    decision = plan_rules.decide_next(history, accept_larger)
    db.add(PlanWeek(case_id=case.id, week_index=week.week_index + 1, action_key=decision.action_key.value,
                    size=decision.size.value, offered_larger=decision.offer_larger, starts_at=now))
    log(db, case, now, EventType.PLAN_WEEK_LAPSED if auto else EventType.PLAN_CHECKIN, actor,
        payload={"week": week.week_index, "status": status.value, "barrier": barrier, "next_size": decision.size.value,
                 "next_action": decision.action_key.value, "shrunk": decision.shrunk, "offer_larger": decision.offer_larger})
    if decision.call_offer and open_task(db, case.id, "PLAN_CALL_OFFER") is None:
        add_task(db, case, now, "PLAN_CALL_OFFER", "offer_a_call", "coordinator", default_owner(db, case, Role.COORDINATOR))
    return {"decision": decision, "texts": wording_port.plan_text(decision.action_key.value, decision.size.value)}


# ------------------------------------------------------------------ evaluation and tick


def alternate_channel(channel: str) -> str:
    return "SMS" if channel in ("APP", "WHATSAPP") else "WHATSAPP"


def refresh_case(db: Session, case: Case, now: datetime) -> engine.Evaluation | None:
    """Evaluate the case at `now` and write any new effects. Never closes a case."""
    if case.state == State.CLOSED.value:
        return None
    week = open_week(db, case.id) if case.state == State.IN_CARE.value else None
    if week is not None and plan_rules.week_lapsed(week.starts_at, now):
        record_checkin(db, case, week, CheckinStatus.MISSED, now, auto=True)

    ev = engine.evaluate(case_data(db, case), now)
    patient = db.get(Patient, case.patient_id)
    for fx in ev.effects:
        kind = fx.kind
        if kind is EffectKind.ESCALATE_LEVEL_1:
            case.escalation_level = 1
            log(db, case, now, EventType.ESCALATED, payload={"level": 1, **fx.payload})
        elif kind is EffectKind.ESCALATE_LEVEL_2:
            case.escalation_level = 2
            log(db, case, now, EventType.ESCALATED, payload={"level": 2, **fx.payload})
        elif kind is EffectKind.ESCALATE_URGENT_REVIEW:
            case.urgent_review_escalated = True
            log(db, case, now, EventType.ESCALATED, payload={"level": 2, "task": "urgent_review", **fx.payload})
        elif kind is EffectKind.UNREACHABLE_REMINDER:
            case.unreachable_stage = 1
            send_template(db, case, now, "reminder_ack")
            log(db, case, now, EventType.UNREACHABLE_STEP, payload={"stage": 1, "action": "reminder"})
        elif kind is EffectKind.UNREACHABLE_SECOND_CHANNEL:
            case.unreachable_stage = 2
            send_template(db, case, now, "reminder_ack", channel=alternate_channel(patient.channel))
            log(db, case, now, EventType.UNREACHABLE_STEP, payload={"stage": 2, "action": "second_channel"})
        elif kind is EffectKind.UNREACHABLE_CALL_TASK:
            case.unreachable_stage = 3
            if open_task(db, case.id, "COORDINATOR_CALL") is None:
                add_task(db, case, now, "COORDINATOR_CALL", "call_the_patient", "coordinator", default_owner(db, case, Role.COORDINATOR))
            log(db, case, now, EventType.UNREACHABLE_STEP, payload={"stage": 3, "action": "call_task"})
        elif kind is EffectKind.UNREACHABLE_CLINICIAN_DECISION:
            case.unreachable_stage = 4
            case.needs_clinician_decision = True
            case.suggested_closure_type = case.suggested_closure_type or "UNREACHABLE_AFTER_PROTOCOL"
            if open_task(db, case.id, "CLINICIAN_DECISION") is None:
                add_task(db, case, now, "CLINICIAN_DECISION", "decide_unreachable_patient", "clinician",
                         _active(db, patient.primary_clinician_id))
            log(db, case, now, EventType.UNREACHABLE_STEP, payload={"stage": 4, "action": "clinician_decision"})
    return ev


def tick_all(db: Session, now: datetime) -> int:
    n = 0
    for case in db.scalars(select(Case).where(Case.state != State.CLOSED.value)):
        refresh_case(db, case, now)
        n += 1
    db.commit()
    return n


def messages_of(db: Session, case_id: int) -> list[Message]:
    return list(db.scalars(select(Message).where(Message.case_id == case_id).order_by(Message.created_at, Message.id)))


def pending_econsults(db: Session, case_id: int) -> list[EConsult]:
    return list(db.scalars(select(EConsult).where(EConsult.case_id == case_id).order_by(EConsult.id)))
