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
from app.engine.demographics import age_band
from app.engine.types import Action, EventType, Role, Severity, State, STATE_ORDER
from app.engine import queues

from . import i18n
from . import schemas as S
from . import wording_port
from .core import (
    appointment_of, case_data, messages_of, plan_active, plan_weeks, reading_data, readings_of, referrals_of, split_name,
    user_name,
)
from .regions import REGIONS, emergency_text

PATIENT_EVENTS = {
    EventType.CASE_OPENED, EventType.MESSAGE_SENT, EventType.TEACH_BACK_PASSED, EventType.CONFIRMATION_REVIEWED,
    EventType.REFERRAL_SENT, EventType.REFERRAL_ACCEPTED, EventType.APPOINTMENT_BOOKED, EventType.VISIT_RECORDED,
    EventType.PLAN_CHECKIN, EventType.CASE_CLOSED, EventType.CONSENT_CHANGED,
}

# Events whose free-text reason is a clinical note. Coordinators see that the event happened, who did it and when, not the note.
CLINICAL_NOTE_EVENTS = {
    EventType.CASE_CLOSED, EventType.VISIT_RECORDED, EventType.URGENT_REVIEW_COMPLETED, EventType.CONFIRMATION_REVIEWED,
    EventType.REFERRAL_SENT, EventType.ECONSULT_ASKED, EventType.ECONSULT_ANSWERED,
}
_NOTE_KEYS = ("note", "question", "answer", "decision_note")

REASON_TEXT = {
    "CARE_COORDINATION_WITHDRAWN": "Patient withdrew permission for care coordination, clinician decision needed",
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


def person(db: Session, user_id: int | None) -> S.PersonRef | None:
    """A staff member as separate name and role (the stored display string carries the role in brackets)."""
    if user_id is None:
        return None
    u = db.get(User, user_id)
    if u is None:
        return None
    return person_from_name(u.name, u.role)


def person_from_name(full: str, fallback_role: str = "") -> S.PersonRef:
    """A person from a stored display string, for example a provider name on a slot or appointment."""
    name, role = split_name(full, fallback_role)
    return S.PersonRef(name=name, role=role, names=S.I18nText(**i18n.person_names(full)),
                       roles=S.I18nText(**i18n.person_roles(full, fallback_role)))


def appointment_label(starts_at, provider: str, location: str, region: str) -> S.I18nText:
    """`25 November, 09:30, Dr Omar, <place>` in each language, on the region's clock."""
    from .message_slots import format_date
    from .regions import tz_of
    local = starts_at.astimezone(tz_of(region))
    who, where = i18n.person_names(provider), i18n.place(location)
    return S.I18nText(**{lang: f"{format_date(local, lang)}, {local.strftime('%H:%M')}, {who[lang]}, {where[lang]}" for lang in i18n.LANGS})


def _last_event(db: Session, case_id: int, types: list[str]) -> CaseEvent | None:
    return db.scalars(select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.type.in_(types))
                      .order_by(CaseEvent.at.desc(), CaseEvent.id.desc())).first()


def _contact_label(e: CaseEvent) -> str:
    return e.payload.get("action", e.type).upper() if e.type == EventType.UNREACHABLE_STEP.value else e.type


def summary_of(db: Session, case: Case, ev: engine.Evaluation, cd) -> S.CaseSummary:
    """One queue row. Coordinator-safe: no clinical notes. The list never needs the detail route."""
    patient = db.get(Patient, case.patient_id)
    flags = flags_of(cd, ev, case)
    code = reason_code(cd, ev, flags)
    step = ev.next_step
    ref = referrals_of(db, case.id)
    rejection = ref[-1].rejection_reason if flags.rejected and ref else None
    escalation = None
    if ev.escalation_level >= 1 and case.state != State.CLOSED.value:
        last_esc = _last_event(db, case.id, [EventType.ESCALATED.value])
        if last_esc is not None:
            escalation = last_esc.reason or f"Step overdue, escalated to {last_esc.payload.get('target') or 'the owner'}"
    contact = _last_event(db, case.id, [EventType.MESSAGE_SENT.value, EventType.MESSAGE_SUPPRESSED.value, EventType.UNREACHABLE_STEP.value])
    text = REASON_TEXT[code]
    if code == "REFERRAL_REJECTED" and rejection:
        text = f"Referral rejected: {rejection}"
    elif code == "ESCALATED" and escalation:
        text = f"Escalated: {escalation}"
    return S.CaseSummary(
        id=case.id, patient_initials=patient.initials, patient_ref=patient.ref, region=case.region, language=patient.language,
        state=case.state, severity=case.severity, urgent=case.urgent, owner_role=case.owner_role,
        owner_user_id=case.owner_user_id, owner_name=user_name(db, case.owner_user_id), owner_person=person(db, case.owner_user_id),
        patient_names=S.I18nText(**i18n.person_names(patient.display_name)),
        patient_initials_i18n=S.I18nText(**i18n.initials_i18n(patient.display_name)),
        age_band=age_band(patient.age),
        next_step_label_key=step.label_key if step else None, due_at=step.due_at if step else None,
        overdue=ev.overdue, overdue_hours=round(ev.overdue_hours, 1), escalation_level=ev.escalation_level,
        reason_code=code, reason_text=text, rejection_reason=rejection, escalation_reason=escalation,
        last_contact_attempt_at=contact.at if contact else None,
        last_contact_attempt=_contact_label(contact) if contact else None,
        flags=flags, index_systolic=case.index_systolic, index_diastolic=case.index_diastolic, opened_at=case.opened_at,
    )


def flags_of(cd, ev: engine.Evaluation, case: Case | None = None) -> S.CaseFlags:
    closed = cd.state is State.CLOSED
    return S.CaseFlags(
        care_coordination_withdrawn=bool(case is not None and case.care_coordination_withdrawn and not closed),
        overdue=ev.overdue, unowned=(not closed and cd.owner_user_id is None and not queues.is_rejected(cd)),
        rejected=queues.is_rejected(cd), escalated=ev.escalation_level >= 2, needs_clinician_decision=cd.needs_clinician_decision,
        closure_ready=cd.closure_ready, urgent_review_pending=engine.sla.urgent_review_pending(cd),
    )


def reason_code(cd, ev, flags: S.CaseFlags) -> str:
    if cd.state is State.CLOSED:
        return "CLOSED"
    if cd.urgent:
        return "URGENT_SEVERE" if cd.severity is Severity.SEVERE else "URGENT_RED_FLAG"
    if flags.care_coordination_withdrawn:
        return "CARE_COORDINATION_WITHDRAWN"
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


def _referral_out(db: Session, r, patient_view: bool, hide_reason: bool = False) -> S.ReferralOut:
    return S.ReferralOut(
        id=r.id, status=r.status, to_user_id=r.to_user_id, to_name=user_name(db, r.to_user_id), to_person=person(db, r.to_user_id),
        to_service=r.to_service, to_service_i18n=S.I18nText(**i18n.service(r.to_service)) if r.to_service else None, from_name=user_name(db, r.from_user_id), from_person=person(db, r.from_user_id),
        reason="" if (patient_view or hide_reason) else r.reason,
        rejection_reason=None if patient_view else r.rejection_reason, created_at=r.created_at, decided_at=r.decided_at,
    )


def _message_out(db: Session, m) -> S.MessageOut:
    return S.MessageOut(
        id=m.id, direction=m.direction, channel=m.channel, language=m.language, text=m.text, template_id=m.template_id,
        template_version=m.template_version, source=m.source, sender_name=user_name(db, m.sender_user_id),
        sender_person=person(db, m.sender_user_id), approved_by_name=user_name(db, m.approved_by_user_id),
        approved_by_person=person(db, m.approved_by_user_id), created_at=m.created_at,
    )


def econsult_out(db: Session, e: EConsult) -> S.EConsultOut:
    return S.EConsultOut(
        id=e.id, case_id=e.case_id, from_user_id=e.from_user_id, from_name=user_name(db, e.from_user_id) or "",
        from_person=person(db, e.from_user_id) or person_from_name("", ""),
        to_user_id=e.to_user_id, to_name=user_name(db, e.to_user_id) or "",
        to_person=person(db, e.to_user_id) or person_from_name("", ""), question=e.question, answer=e.answer,
        status=e.status, created_at=e.created_at, answered_at=e.answered_at,
    )


def message_list(db: Session, case_id: int) -> list[S.MessageOut]:
    from .intake import valid_replies
    out = [_message_out(db, m) for m in messages_of(db, case_id)]
    case = db.get(Case, case_id)
    last = next((m for m in reversed(out) if m.direction == "OUT"), None)
    if last is not None and case is not None and case.state != State.CLOSED.value:
        last.valid_replies = [S.ReplyOption(reply=r, meaning_key=k) for r, k in valid_replies(db, case)]
    return out


def _urgent_due(db: Session, case: Case):
    if not case.urgent or case.urgent_review_done_at is not None:
        return None
    t = db.scalars(select(Task).where(Task.case_id == case.id, Task.type == "URGENT_REVIEW", Task.status == "OPEN")
                   .order_by(Task.id.desc())).first()
    return t.due_at if t else None


def _teach_back(db: Session, case: Case, patient: Patient, cd, language: str | None = None) -> S.TeachBackOut | None:
    if cd.state is not State.NOTIFIED:
        return None
    from .core import slots_for
    lang = language or patient.language
    tb = wording_port.teach_back(lang, slots_for(db, case, language=lang, template_id="teach_back_question"), sms=False, app=True)
    return S.TeachBackOut(question=tb["question"], options=list(tb["options"]), simpler=tb["simpler"], language=lang)


def case_detail(db: Session, case: Case, viewer: User, role: Role, now: datetime, *, patient_view: bool = False,
                language: str | None = None) -> S.CaseDetail:
    """Case detail for one viewer. A coordinator gets no clinical free text (notes, e-consult content); `language` is for the patient view."""
    from .regions import tz_of
    cd = case_data(db, case)
    ev = engine.evaluate(cd, now)
    patient = db.get(Patient, case.patient_id)
    step = ev.next_step
    flags = flags_of(cd, ev, case)
    rows = readings_of(db, case.id)
    conf = engine.evaluate_confirmation(cd.confirmation_method, reading_data(rows), tz_of(case.region))
    minimise = role is Role.COORDINATOR  # data minimisation: operational view only
    plan_lang = language or patient.language
    refs = referrals_of(db, case.id)
    appt = appointment_of(db, case.id)

    events = list(db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.at, CaseEvent.id)))
    timeline = []
    for e in events:
        if patient_view and EventType(e.type) not in PATIENT_EVENTS:
            continue
        who = ("Care team" if e.actor_role != "patient" else "You") if patient_view else (user_name(db, e.actor_user_id) or "System")
        hide_note = minimise and EventType(e.type) in CLINICAL_NOTE_EVENTS
        payload = {k: v for k, v in e.payload.items() if k not in _NOTE_KEYS} if hide_note else e.payload
        timeline.append(S.EventOut(id=e.id, at=e.at, actor_name=who, actor_person=None if patient_view else person(db, e.actor_user_id),
                                   actor_role=e.actor_role, type=e.type,
                                   from_state=e.from_state, to_state=e.to_state,
                                   payload={} if patient_view else payload, reason=None if (patient_view or hide_note) else e.reason))

    tasks, econs = [], []
    if not patient_view:
        for t in db.scalars(select(Task).where(Task.case_id == case.id).order_by(Task.id)):
            tasks.append(S.TaskOut(title_i18n=S.I18nText(**i18n.task_title(t.title_key)), id=t.id, type=t.type, title_key=t.title_key, owner_role=t.owner_role, owner_user_id=t.owner_user_id,
                                   due_at=t.due_at, status=t.status, overdue=bool(t.status == "OPEN" and t.due_at and now > t.due_at),
                                   created_at=t.created_at))
        if role is not Role.COORDINATOR:
            econs = [econsult_out(db, e) for e in db.scalars(select(EConsult).where(EConsult.case_id == case.id).order_by(EConsult.id))]

    closure = None
    if case.state == State.CLOSED.value and case.closure_evidence_type:
        closure = S.ClosureOut(closed_at=case.closed_at, closed_by_name=user_name(db, case.closed_by_user_id),
                               closed_by_person=person(db, case.closed_by_user_id),
                               evidence_type=case.closure_evidence_type, evidence_ref=case.closure_evidence_ref,
                               decision_note=None if (patient_view or minimise) else case.closure_decision_note)

    advice = None
    if case.state != State.CLOSED.value and (case.urgent or case.severity == Severity.SEVERE.value):
        advice = S.EmergencyAdvice(text=emergency_text(case.region, patient.language),
                                   text_i18n=S.I18nText(**{lang: emergency_text(case.region, lang) for lang in i18n.LANGS}), number=REGIONS[case.region]["emergency_number"],
                                   region=case.region)

    next_out = None
    if step:
        next_out = S.NextStepOut(
            label_key=step.label_key, owner_role=step.owner_role.value, acting_role=step.acting_role.value,
            owner_user_id=case.owner_user_id, owner_name=user_name(db, case.owner_user_id), owner_person=person(db, case.owner_user_id),
            started_at=step.started_at,
            due_at=step.due_at, service_level_h=step.service_level_h, overdue=ev.overdue, overdue_hours=round(ev.overdue_hours, 1),
            escalation_level=0 if patient_view else ev.escalation_level, escalation_target=None if patient_view else ev.escalation_target,
        )

    weeks = [
        S.PlanWeekOut(week_index=w.week_index, action_key=w.action_key, size=w.size, status=w.status, barrier=w.barrier,
                      offered_larger=w.offered_larger, starts_at=w.starts_at, checked_in_at=w.checked_in_at,
                      label_key=f"plan.{w.action_key}.{w.size}", default_text=wording_port.plan_text(w.action_key, w.size, plan_lang),
                      default_text_i18n=S.I18nText(**{lang: wording_port.plan_text(w.action_key, w.size, lang) for lang in i18n.LANGS}))
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
                                 channel=patient.channel, organisation=patient.organisation,
                                 names=S.I18nText(**i18n.person_names(patient.display_name)),
                                 initials_i18n=S.I18nText(**i18n.initials_i18n(patient.display_name)),
                                 organisation_i18n=S.I18nText(**i18n.place(patient.organisation)),
                                 region_name_i18n=S.I18nText(**i18n.region_names(patient.region))),
        owner_role=case.owner_role, owner_user_id=case.owner_user_id, owner_name=user_name(db, case.owner_user_id),
        owner_person=person(db, case.owner_user_id), plan_active=plan_active(db, case),
        urgent_review_due_at=None if patient_view else _urgent_due(db, case),
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
        referral=_referral_out(db, refs[-1], patient_view, minimise) if refs else None,
        referrals_history=[] if patient_view else [_referral_out(db, r, False, minimise) for r in refs[:-1]],
        appointment=S.AppointmentOut(id=appt.id, starts_at=appt.starts_at, provider_name=appt.provider_name, location=appt.location,
                                     status=appt.status, provider_name_i18n=S.I18nText(**i18n.person_names(appt.provider_name)),
                                     provider_person=person_from_name(appt.provider_name, "clinician"),
                                     location_i18n=S.I18nText(**i18n.place(appt.location)),
                                     label_i18n=appointment_label(appt.starts_at, appt.provider_name, appt.location, case.region)) if appt else None,
        messages=message_list(db, case.id), econsults=econs, plan=weeks, consents=consents, tasks=tasks, timeline=timeline,
        closure=closure,
        allowed_actions=[a for a in engine.allowed_actions(cd, Role(role), viewer.id if viewer else None)
                         if a is not Action.PLAN_CHECKIN or plan_active(db, case)],
        emergency_advice=advice, teach_back=_teach_back(db, case, patient, cd, language), view="PATIENT" if patient_view else "STAFF",
    )
