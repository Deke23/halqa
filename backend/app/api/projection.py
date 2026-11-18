"""Row to response projections, including the patient-safe view.

Safety property: the patient view omits staff-only content (tasks, e-consults, rejection
reasons, closure notes, escalation state, audit payloads) and shows plan and result text
without diagnosis words.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Case, CaseEvent, Consent, EConsult, Patient, Task, User
from app.engine.types import EventType, Role, Severity, State, STATE_ORDER
from app.engine import queues

from . import schemas as S
from . import wording_port
from .core import (
    appointment_of, case_data, messages_of, plan_weeks, reading_data, readings_of, referrals_of, user_name,
)
from .regions import REGIONS, emergency_text

PATIENT_EVENTS = {
    EventType.CASE_OPENED, EventType.MESSAGE_SENT, EventType.TEACH_BACK_PASSED, EventType.CONFIRMATION_REVIEWED,
    EventType.REFERRAL_SENT, EventType.REFERRAL_ACCEPTED, EventType.APPOINTMENT_BOOKED, EventType.VISIT_RECORDED,
    EventType.PLAN_CHECKIN, EventType.CASE_CLOSED, EventType.CONSENT_CHANGED,
}

REASON_TEXT = {
    "URGENT_SEVERE": "Severe reading, same-day clinician review",
    "URGENT_RED_FLAG": "Patient reported a warning symptom",
    "REFERRAL_REJECTED": "Referral rejected, needs a new owner or referral",
    "NO_OWNER": "No owner for the current step",
    "ESCALATED": "Escalated",
    "NEEDS_CLINICIAN_DECISION": "Patient not reached after the contact steps, clinician decision needed",
    "OVERDUE": "Step is overdue",
    "READY_TO_CLOSE": "Last readings at target, waiting for clinician closure",
    "ON_TRACK": "On track",
    "CLOSED": "Closed",
}


def summary_of(db: Session, case: Case, ev: engine.Evaluation, cd) -> S.CaseSummary:
    patient = db.get(Patient, case.patient_id)
    flags = flags_of(cd, ev)
    code = reason_code(cd, ev, flags)
    step = ev.next_step
    return S.CaseSummary(
        id=case.id, patient_initials=patient.initials, patient_ref=patient.ref, region=case.region, language=patient.language,
        state=case.state, severity=case.severity, urgent=case.urgent, owner_role=case.owner_role,
        owner_user_id=case.owner_user_id, owner_name=user_name(db, case.owner_user_id),
        next_step_label_key=step.label_key if step else None, due_at=step.due_at if step else None,
        overdue=ev.overdue, overdue_hours=round(ev.overdue_hours, 1), escalation_level=ev.escalation_level,
        reason_code=code, reason_text=REASON_TEXT[code], flags=flags, index_systolic=case.index_systolic,
        index_diastolic=case.index_diastolic, opened_at=case.opened_at,
    )


def flags_of(cd, ev: engine.Evaluation) -> S.CaseFlags:
    closed = cd.state is State.CLOSED
    return S.CaseFlags(
        overdue=ev.overdue, unowned=(not closed and cd.owner_user_id is None and not queues.is_rejected(cd)),
        rejected=queues.is_rejected(cd), escalated=ev.escalation_level >= 2, needs_clinician_decision=cd.needs_clinician_decision,
        closure_ready=cd.closure_ready, urgent_review_pending=engine.sla.urgent_review_pending(cd),
    )


def reason_code(cd, ev, flags: S.CaseFlags) -> str:
    if cd.state is State.CLOSED:
        return "CLOSED"
    if cd.urgent:
        return "URGENT_SEVERE" if cd.severity is Severity.SEVERE else "URGENT_RED_FLAG"
    for flag, code in ((flags.rejected, "REFERRAL_REJECTED"), (flags.unowned, "NO_OWNER"), (flags.escalated, "ESCALATED"),
                       (flags.needs_clinician_decision, "NEEDS_CLINICIAN_DECISION"), (flags.overdue, "OVERDUE"),
                       (flags.closure_ready, "READY_TO_CLOSE")):
        if flag:
            return code
    return "ON_TRACK"


def _progress(case: Case) -> list[S.ProgressStep]:
    ms = case.milestones or {}
    cur = STATE_ORDER.index(State(case.state))
    out = []
    for i, st in enumerate(STATE_ORDER):
        at = ms.get(st.value)
        out.append(S.ProgressStep(state=st, label_key=f"step.{st.value.lower()}", reached=i <= cur, current=i == cur,
                                  reached_at=datetime.fromisoformat(at) if at and i <= cur else None))
    return out


def _referral_out(db: Session, r, patient_view: bool) -> S.ReferralOut:
    return S.ReferralOut(
        id=r.id, status=r.status, to_user_id=r.to_user_id, to_name=user_name(db, r.to_user_id), to_service=r.to_service,
        from_name=user_name(db, r.from_user_id), reason="" if patient_view else r.reason,
        rejection_reason=None if patient_view else r.rejection_reason, created_at=r.created_at, decided_at=r.decided_at,
    )


def _message_out(db: Session, m) -> S.MessageOut:
    return S.MessageOut(
        id=m.id, direction=m.direction, channel=m.channel, language=m.language, text=m.text, template_id=m.template_id,
        template_version=m.template_version, source=m.source, sender_name=user_name(db, m.sender_user_id),
        approved_by_name=user_name(db, m.approved_by_user_id), created_at=m.created_at,
    )


def econsult_out(db: Session, e: EConsult) -> S.EConsultOut:
    return S.EConsultOut(
        id=e.id, case_id=e.case_id, from_user_id=e.from_user_id, from_name=user_name(db, e.from_user_id) or "",
        to_user_id=e.to_user_id, to_name=user_name(db, e.to_user_id) or "", question=e.question, answer=e.answer,
        status=e.status, created_at=e.created_at, answered_at=e.answered_at,
    )


def message_list(db: Session, case_id: int) -> list[S.MessageOut]:
    return [_message_out(db, m) for m in messages_of(db, case_id)]


def _teach_back(db: Session, case: Case, patient: Patient, cd) -> S.TeachBackOut | None:
    if cd.state is not State.NOTIFIED:
        return None
    from .core import slots_for
    tb = wording_port.teach_back(patient.language, slots_for(db, case), sms=False)
    return S.TeachBackOut(question=tb["question"], options=list(tb["options"]), language=patient.language)


def case_detail(db: Session, case: Case, viewer: User, role: Role, now: datetime, *, patient_view: bool = False) -> S.CaseDetail:
    cd = case_data(db, case)
    ev = engine.evaluate(cd, now)
    patient = db.get(Patient, case.patient_id)
    step = ev.next_step
    flags = flags_of(cd, ev)
    rows = readings_of(db, case.id)
    conf = engine.evaluate_confirmation(cd.confirmation_method, reading_data(rows))
    refs = referrals_of(db, case.id)
    appt = appointment_of(db, case.id)

    events = list(db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.at, CaseEvent.id)))
    timeline = []
    for e in events:
        if patient_view and EventType(e.type) not in PATIENT_EVENTS:
            continue
        who = ("Care team" if e.actor_role != "patient" else "You") if patient_view else (user_name(db, e.actor_user_id) or "System")
        timeline.append(S.EventOut(id=e.id, at=e.at, actor_name=who, actor_role=e.actor_role, type=e.type,
                                   from_state=e.from_state, to_state=e.to_state,
                                   payload={} if patient_view else e.payload, reason=None if patient_view else e.reason))

    tasks, econs = [], []
    if not patient_view:
        for t in db.scalars(select(Task).where(Task.case_id == case.id).order_by(Task.id)):
            tasks.append(S.TaskOut(id=t.id, type=t.type, title_key=t.title_key, owner_role=t.owner_role, owner_user_id=t.owner_user_id,
                                   due_at=t.due_at, status=t.status, overdue=bool(t.status == "OPEN" and t.due_at and now > t.due_at),
                                   created_at=t.created_at))
        if role is not Role.COORDINATOR:
            econs = [econsult_out(db, e) for e in db.scalars(select(EConsult).where(EConsult.case_id == case.id).order_by(EConsult.id))]

    closure = None
    if case.state == State.CLOSED.value and case.closure_evidence_type:
        closure = S.ClosureOut(closed_at=case.closed_at, closed_by_name=user_name(db, case.closed_by_user_id),
                               evidence_type=case.closure_evidence_type, evidence_ref=case.closure_evidence_ref,
                               decision_note=None if patient_view else case.closure_decision_note)

    advice = None
    if case.state != State.CLOSED.value and (case.urgent or case.severity == Severity.SEVERE.value):
        advice = S.EmergencyAdvice(text=emergency_text(case.region, patient.language), number=REGIONS[case.region]["emergency_number"],
                                   region=case.region)

    next_out = None
    if step:
        next_out = S.NextStepOut(
            label_key=step.label_key, owner_role=step.owner_role.value, acting_role=step.acting_role.value,
            owner_user_id=case.owner_user_id, owner_name=user_name(db, case.owner_user_id), started_at=step.started_at,
            due_at=step.due_at, service_level_h=step.service_level_h, overdue=ev.overdue, overdue_hours=round(ev.overdue_hours, 1),
            escalation_level=0 if patient_view else ev.escalation_level, escalation_target=None if patient_view else ev.escalation_target,
        )

    weeks = [
        S.PlanWeekOut(week_index=w.week_index, action_key=w.action_key, size=w.size, status=w.status, barrier=w.barrier,
                      offered_larger=w.offered_larger, starts_at=w.starts_at, checked_in_at=w.checked_in_at,
                      label_key=f"plan.{w.action_key}.{w.size}", default_text=wording_port.plan_text(w.action_key, w.size))
        for w in plan_weeks(db, case.id)
    ]
    consents = [S.ConsentOut(purpose=c.purpose, channel=c.channel, granted=c.granted, granted_at=c.granted_at, withdrawn_at=c.withdrawn_at)
                for c in db.scalars(select(Consent).where(Consent.patient_id == patient.id).order_by(Consent.id))]

    if patient_view:
        flags = S.CaseFlags(overdue=False, unowned=False, rejected=False, escalated=False, needs_clinician_decision=False,
                            closure_ready=False, urgent_review_pending=False)

    return S.CaseDetail(
        id=case.id, state=case.state, severity=case.severity, urgent=case.urgent,
        urgent_reason=None if patient_view else case.urgent_reason, region=case.region, opened_at=case.opened_at,
        index_systolic=case.index_systolic, index_diastolic=case.index_diastolic, source_system=case.source_system,
        patient=S.PatientSummary(id=patient.id, ref=patient.ref, display_name=patient.display_name, initials=patient.initials,
                                 age=patient.age, sex=patient.sex, nationality_group=patient.nationality_group,
                                 language=patient.language, region=patient.region, insurance=patient.insurance,
                                 channel=patient.channel, organisation=patient.organisation),
        owner_role=case.owner_role, owner_user_id=case.owner_user_id, owner_name=user_name(db, case.owner_user_id),
        next_step=next_out, progress=_progress(case), flags=flags, referral_status=case.referral_status,
        suggested_closure_type=None if patient_view else case.suggested_closure_type,
        readings=[S.ReadingOut(id=r.id, systolic=r.systolic, diastolic=r.diastolic, pulse=r.pulse, taken_at=r.taken_at,
                               source=r.source, entered_by_role=r.entered_by_role) for r in rows],
        confirmation=None if (conf is None and cd.confirmation_method is None) else S.ConfirmationOut(
            method=cd.confirmation_method, status=conf.status if conf else None,
            average_systolic=conf.average_systolic if conf else None, average_diastolic=conf.average_diastolic if conf else None,
            days_counted=conf.days_counted if conf else 0, readings_used=conf.readings_used if conf else 0,
            days_with_enough_readings=conf.days_with_enough_readings if conf else 0, days_required=conf.days_required if conf else 0,
            threshold_status="placeholder_pending_clinician_signoff"),
        referral=_referral_out(db, refs[-1], patient_view) if refs else None,
        referrals_history=[] if patient_view else [_referral_out(db, r, False) for r in refs[:-1]],
        appointment=S.AppointmentOut(id=appt.id, starts_at=appt.starts_at, provider_name=appt.provider_name, location=appt.location,
                                     status=appt.status) if appt else None,
        messages=message_list(db, case.id), econsults=econs, plan=weeks, consents=consents, tasks=tasks, timeline=timeline,
        closure=closure,
        allowed_actions=engine.allowed_actions(cd, Role(role), viewer.id if viewer else None),
        emergency_advice=advice, teach_back=_teach_back(db, case, patient, cd), view="PATIENT" if patient_view else "STAFF",
    )
