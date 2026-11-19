"""Shared case helpers: snapshots for the engine, event log, owners, messages, tick.

This module is the bridge between rows and the pure engine. Every decision is the engine's;
this code only reads rows into a `CaseData`, then writes what the engine returned.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import (
    Appointment, Case, CaseEvent, Consent, EConsult, Message, MessageDraft, Patient, PlanWeek, Reading, Referral, Task, User,
)
from app.engine import plan as plan_rules
from app.engine.types import (
    CaseData, CheckinStatus, ConfirmationMethod, ConfirmationStatus, EffectKind, EventType, PlanActionKey,
    PlanSize, ReadingData, ReadingSource, ReferralStatus, Role, Severity, State, STATE_ORDER,
)

from . import message_slots, wording_port
from .regions import tz_of

log_ = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


# ------------------------------------------------------------------ lookups


_BRACKETED = re.compile(r"^(.*?)\s*\((.*)\)\s*$")


def split_name(full: str, fallback_role: str = "") -> tuple[str, str]:
    """`Clarisse (nurse coordinator)` becomes (`Clarisse`, `nurse coordinator`). Without brackets the role is the fallback."""
    m = _BRACKETED.match(full)
    return (m.group(1), m.group(2)) if m else (full, fallback_role)


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


def explicit_consent(db: Session, patient_id: int, purpose: str, channel: str | None = None) -> bool:
    """True only when a matching consent record exists and is granted. A missing record is NOT consent."""
    q = select(Consent).where(Consent.patient_id == patient_id, Consent.purpose == purpose)
    if channel:
        q = q.where(Consent.channel == channel)
    rows = list(db.scalars(q))
    return bool(rows) and all(c.granted for c in rows)


def plan_active(db: Session, case: Case) -> bool:
    """A lifestyle plan only runs while the case is in care and the patient has not withdrawn lifestyle_programme."""
    return case.state == State.IN_CARE.value and consent_granted(db, case.patient_id, "lifestyle_programme")


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
    conf = engine.evaluate_confirmation(method, rdata, tz_of(case.region))
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
#
# Every outbound message goes through `send_message`, the single place that checks consent, renders (or takes a
# server-stored draft), stores the slots, writes the audit event and, when consent is withdrawn, records the suppression.

AUTOMATED = "AUTOMATED"          # system notices, reminders, referral and appointment notices, weekly actions
STAFF = "STAFF"                  # a staff member sends an approved template or a validated draft
REPLY = "REPLY"                  # immediate reply to something the patient did or sent
SAFETY_REPLY = "SAFETY_REPLY"    # emergency advice answering the patient's own message; sent even if consent was withdrawn
FINAL = "FINAL"                  # the one fixed confirmation after STOP; sent after the channel consent was withdrawn

LIFESTYLE_TEMPLATES = frozenset({"weekly_action", "no_blame_checkin", "plan_smaller"})

# The late patient step decides the reminder wording (acknowledge, home readings, booking). The appointment reminder is
# sent before the visit by the tick, see `refresh_case`.
REMINDER_BY_STEP = {
    "patient_acknowledge": "reminder_ack",
    "choose_confirmation_method": "reminder_home_readings",
    "complete_home_readings": "reminder_home_readings",
    "attend_abpm": "reminder_home_readings",
    "book_appointment": "reminder_booking",
}


def reminder_template_for(step_label: str | None) -> str:
    return REMINDER_BY_STEP.get(step_label or "", "reminder_ack")


def first_name(patient: Patient) -> str:
    return patient.display_name.split()[0]


def neutral_slots(db: Session, case: Case, template_id: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Language-neutral slot values for a message about this case, as of now. Dates are ISO timestamps (UTC)."""
    patient = db.get(Patient, case.patient_id)
    rows = readings_of(db, case.id)
    last = rows[-1] if rows else None
    if message_slots.base_template_id(template_id) in message_slots.INDEX_READING_TEMPLATES or last is None:
        s, d = case.index_systolic, case.index_diastolic
    else:
        s, d = last.systolic, last.diastolic
    step = engine.next_step(case_data(db, case))
    review = (case.urgent_started_at + timedelta(hours=engine.config.hours("service_levels", "urgent_review"))
              if case.urgent_started_at else None)
    neutral: dict[str, Any] = {
        "name": first_name(patient), "systolic": s, "diastolic": d, "reading": f"{s}/{d}", "phone": patient.phone or "",
        "clinic": patient.organisation, "provider": "", "due_at": message_slots.to_iso(step.due_at if step else None),
        "review_at": message_slots.to_iso(review), "appointment_at": None, "closed_at": message_slots.to_iso(case.closed_at),
        "closure_reason": "", "plan": None,
    }
    appt = appointment_of(db, case.id)
    if appt:
        neutral.update(appointment_at=message_slots.to_iso(appt.starts_at), clinic=appt.location, provider=appt.provider_name)
    neutral.update(extra or {})
    return neutral


def slots_for(db: Session, case: Case, extra: dict[str, Any] | None = None, language: str | None = None,
              template_id: str = "") -> dict[str, Any]:
    """Template slots in one language (default: the patient's) on the region's local clock. `extra` holds neutral values."""
    patient = db.get(Patient, case.patient_id)
    return message_slots.localize(neutral_slots(db, case, template_id, extra), language or patient.language, case.region)


@dataclass
class Prepared:
    """A message whose text was already produced and checked on the server (a stored draft)."""

    text: str
    version: str
    source: str
    neutral: dict[str, Any]
    validation: dict[str, Any]
    draft_id: int
    approved_by: User | None


def add_message(
    db: Session, case: Case, now: datetime, template_id: str | None, text: str, *, language: str, channel: str,
    direction: str = "IN", sender: User | None = None, source: str = "TEMPLATE", version: str | None = None,
    approved_by: User | None = None, slots: dict[str, Any] | None = None, draft_id: int | None = None,
) -> Message:
    """Store a message row. Outbound rows are written only by `send_message`; call this directly for inbound text only."""
    msg = Message(
        case_id=case.id, direction=direction, channel=channel, language=language, text=text, template_id=template_id,
        template_version=version, source=source, sender_user_id=sender.id if sender else None,
        approved_by_user_id=approved_by.id if approved_by else None, created_at=now, slots=slots, draft_id=draft_id,
    )
    db.add(msg)
    return msg


def consent_blocker(db: Session, case: Case, channel: str, kind: str, template_id: str) -> str | None:
    """The consent purpose that stops this message, or None when it may be sent."""
    if kind in (FINAL, SAFETY_REPLY):
        return None
    if not explicit_consent(db, case.patient_id, "messaging_channel", channel):
        return "messaging_channel"
    if not consent_granted(db, case.patient_id, "care_coordination"):
        return "care_coordination"
    if message_slots.base_template_id(template_id) in LIFESTYLE_TEMPLATES and not consent_granted(db, case.patient_id, "lifestyle_programme"):
        return "lifestyle_programme"
    return None


def consented_channels(db: Session, patient_id: int) -> set[str]:
    """Channels with an explicit, currently granted messaging_channel consent."""
    return {c.channel for c in db.scalars(select(Consent).where(Consent.patient_id == patient_id, Consent.purpose == "messaging_channel",
                                                                 Consent.granted.is_(True)))}


def contact_other_route_task(db: Session, case: Case, now: datetime) -> None:
    """One coordinator task "contact by another agreed route", never one per suppressed reminder.

    Only when no consented channel remains at all. While another channel is agreed, a suppressed message is just recorded.
    """
    if consented_channels(db, case.patient_id):
        return
    if open_task(db, case.id, "CONTACT_OTHER_ROUTE") is None:
        add_task(db, case, now, "CONTACT_OTHER_ROUTE", "contact_by_another_agreed_route", "coordinator",
                 default_owner(db, case, Role.COORDINATOR))


def send_message(
    db: Session, case: Case, now: datetime, template_id: str, *, kind: str = AUTOMATED, sender: User | None = None,
    language: str | None = None, channel: str | None = None, extra: dict[str, Any] | None = None,
    prepared: Prepared | None = None, transition: tuple[str, str] | None = None,
) -> Message | None:
    """The single send function. Returns the stored message, or None when it was suppressed.

    1. consent is checked for the channel (and care coordination, and the lifestyle programme for plan messages);
    2. if it is withdrawn, nothing is sent, a MESSAGE_SUPPRESSED event is written and, for a withdrawn channel, one
       coordinator task "contact by another agreed route" is created (not one per suppressed message);
    3. otherwise the text is rendered from the approved template (or taken from a server-stored draft), the neutral
       slots are stored with the message, and a MESSAGE_SENT event records template, source, approver and validation.
    """
    patient = db.get(Patient, case.patient_id)
    lang = language or patient.language
    chan = channel or patient.channel
    blocker = consent_blocker(db, case, chan, kind, template_id)
    if blocker:
        log(db, case, now, EventType.MESSAGE_SUPPRESSED, sender,
            payload={"template_id": template_id, "channel": chan, "language": lang, "kind": kind, "consent_purpose": blocker})
        if blocker == "messaging_channel":
            contact_other_route_task(db, case, now)
        return None

    if prepared is not None:
        neutral, text, version, source = prepared.neutral, prepared.text, prepared.version, prepared.source
        approver, draft_id, validation = prepared.approved_by, prepared.draft_id, prepared.validation
    else:
        neutral = neutral_slots(db, case, template_id, extra)
        out = wording_port.render(template_id, lang, message_slots.localize(neutral, lang, case.region), chan)
        text, version, source, approver, draft_id, validation = out.text, out.template_version, "TEMPLATE", None, None, None
    msg = add_message(db, case, now, template_id, text, language=lang, channel=chan, direction="OUT", sender=sender, source=source,
                      version=version, approved_by=approver, slots=neutral, draft_id=draft_id)
    payload: dict[str, Any] = {"template_id": template_id, "channel": chan, "language": lang, "source": source, "kind": kind}
    if kind == SAFETY_REPLY:
        payload["consent_override"] = "emergency advice answering the patient's own message"
    if approver is not None:
        payload["approved_by_user_id"] = approver.id
    if draft_id is not None:
        payload["draft_id"] = draft_id
        payload["validation"] = validation
    log(db, case, now, EventType.MESSAGE_SENT, sender, payload=payload,
        from_state=transition[0] if transition else None, to_state=transition[1] if transition else None)
    return msg


def send_template(
    db: Session, case: Case, now: datetime, template_id: str, *, sender: User | None = None,
    language: str | None = None, channel: str | None = None, extra: dict[str, Any] | None = None, kind: str = AUTOMATED,
) -> Message | None:
    return send_message(db, case, now, template_id, kind=kind, sender=sender, language=language, channel=channel, extra=extra)


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
    patient = db.get(Patient, case.patient_id)
    return {"decision": decision, "texts": wording_port.plan_text(decision.action_key.value, decision.size.value, patient.language)}


# ------------------------------------------------------------------ evaluation and tick


def alternate_channel(channel: str) -> str:
    return "SMS" if channel in ("APP", "WHATSAPP") else "WHATSAPP"


def refresh_case(db: Session, case: Case, now: datetime) -> engine.Evaluation | None:
    """Evaluate the case at `now` and write any new effects. Never closes a case."""
    if case.state == State.CLOSED.value:
        return None
    # A withdrawn lifestyle_programme stops the running plan: no lapse is recorded and no further weeks are created.
    week = open_week(db, case.id) if plan_active(db, case) else None
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
            send_template(db, case, now, reminder_template_for(fx.payload.get("step")))
            log(db, case, now, EventType.UNREACHABLE_STEP, payload={"stage": 1, "action": "reminder"})
        elif kind is EffectKind.UNREACHABLE_SECOND_CHANNEL:
            case.unreachable_stage = 2
            alt = alternate_channel(patient.channel)
            if explicit_consent(db, patient.id, "messaging_channel", alt):
                send_template(db, case, now, reminder_template_for(fx.payload.get("step")), channel=alt)
            else:  # the next protocol channel was never agreed: record that it was skipped and go on to the next stage
                log(db, case, now, EventType.MESSAGE_SUPPRESSED, payload={
                    "template_id": reminder_template_for(fx.payload.get("step")), "channel": alt, "language": patient.language,
                    "kind": AUTOMATED, "consent_purpose": "messaging_channel", "protocol_stage": 2, "skipped_to_next_stage": True})
                contact_other_route_task(db, case, now)
            log(db, case, now, EventType.UNREACHABLE_STEP, payload={"stage": 2, "action": "second_channel"})
        elif kind is EffectKind.UNREACHABLE_CALL_TASK:
            case.unreachable_stage = 3
            # A patient who withdrew care_coordination is not phoned by a task; the clinician decision below is still created.
            if not case.care_coordination_withdrawn and open_task(db, case.id, "COORDINATOR_CALL") is None:
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
    _appointment_reminder(db, case, now)
    return ev


APPOINTMENT_REMINDER_HOURS = 24


def _appointment_reminder(db: Session, case: Case, now: datetime) -> None:
    """One reminder in the 24 hours before a booked visit, in the patient's language. A suppressed one is not retried."""
    if case.state != State.APPOINTMENT_BOOKED.value:
        return
    appt = appointment_of(db, case.id)
    if appt is None or appt.status != "BOOKED" or not (timedelta(0) < appt.starts_at - now <= timedelta(hours=APPOINTMENT_REMINDER_HOURS)):
        return
    for e in db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id, CaseEvent.at >= appt.created_at,
                                                CaseEvent.type.in_([EventType.MESSAGE_SENT.value, EventType.MESSAGE_SUPPRESSED.value]))):
        if e.payload.get("template_id") == "appointment_reminder":
            return
    send_template(db, case, now, "appointment_reminder")


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
