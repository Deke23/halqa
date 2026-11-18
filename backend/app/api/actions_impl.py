"""Case actions: the only way case state changes.

Order of checks: role (403), state and rules (409), payload (422). The engine decides
what is allowed and what the next state is; this module applies it and writes the audit event.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Appointment, Case, Consent, Patient, Reading, Referral, Slot, User
from app.engine.types import (
    Action, CheckinStatus, ClosureEvidence, ConfirmationMethod, ConfirmationStatus, EventType, ReadingSource,
    ReferralStatus, Role, Severity, State,
)

from . import wording_port
from .core import (
    ApiError, add_message, add_task, begin_step, case_data, complete_tasks, consent_granted, default_owner, flag_urgent,
    log, open_task, open_week, readings_of, reading_data, record_checkin, send_template, set_state, start_plan,
    _active,
)
from .regions import emergency_text
from .schemas import (
    PAYLOAD_MODELS, AcknowledgePayload, AddReadingPayload, AssignOwnerPayload, BookAppointmentPayload, ChooseConfirmationPayload,
    ClosePayload, ConsentPayload, Feedback, NotifyPayload, PlanCheckinPayload, ReasonPayload, RecordVisitPayload, ReferPayload,
    ReviewConfirmationPayload, ReviewOutcome, UrgentReviewPayload, VisitOutcome,
)

SPECIALIST_SERVICE = "hypertension_clinic"


class Ctx:
    def __init__(self, db: Session, case: Case, user: User | None, role: Role, now: datetime) -> None:
        self.db, self.case, self.user, self.role, self.now = db, case, user, role, now
        self.feedback: Feedback | None = None

    def log(self, type_: EventType, **kw: Any) -> None:
        log(self.db, self.case, self.now, type_, self.user, **kw)

    def move(self, to: State) -> str:
        return set_state(self.db, self.case, to, self.now)


def parse_payload(action: Action, raw: dict[str, Any]) -> BaseModel:
    try:
        return PAYLOAD_MODELS[action].model_validate(raw or {})
    except ValidationError as exc:
        detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise ApiError(422, "INVALID_PAYLOAD", detail) from exc


def perform(db: Session, case: Case, user: User | None, role: Role, action: Action, raw: dict[str, Any], now: datetime) -> Feedback | None:
    cd = case_data(db, case)
    verdict = engine.check(action, role, cd, user.id if user else None)
    if not verdict.ok:
        raise ApiError(verdict.status, verdict.code, verdict.message)
    payload = parse_payload(action, raw)
    ctx = Ctx(db, case, user, role, now)
    HANDLERS[action](ctx, payload)
    db.flush()
    return ctx.feedback


# ------------------------------------------------------------------ handlers


def do_notify(ctx: Ctx, p: NotifyPayload) -> None:
    patient = ctx.db.get(Patient, ctx.case.patient_id)
    if not consent_granted(ctx.db, patient.id, "messaging_channel", p.channel.value):
        raise ApiError(409, "CONSENT_WITHDRAWN", "The patient has withdrawn permission for this messaging channel.")
    from .core import slots_for
    out = wording_port.render(p.template_id, p.language.value, slots_for(ctx.db, ctx.case), p.channel.value)
    add_message(ctx.db, ctx.case, ctx.now, p.template_id, out.text, language=p.language.value, channel=p.channel.value,
                sender=ctx.user, version=out.template_version)
    before = ctx.move(State.NOTIFIED)
    begin_step(ctx.db, ctx.case, ctx.now)
    ctx.log(EventType.MESSAGE_SENT, from_state=before, to_state=State.NOTIFIED.value,
            payload={"template_id": p.template_id, "channel": p.channel.value, "language": p.language.value})


def do_acknowledge(ctx: Ctx, p: AcknowledgePayload) -> None:
    case = ctx.case
    emergency = bool(p.red_flags)
    if emergency:
        flag_urgent(ctx.db, case, ctx.now, "RED_FLAG", ctx.user)
        ctx.log(EventType.RED_FLAG_REPORTED, payload={"red_flags": [f.value for f in p.red_flags]})
        ctx.feedback = Feedback(code="RED_FLAG_EMERGENCY", message=emergency_text(case.region, ctx.db.get(Patient, case.patient_id).language))
    from .core import slots_for
    patient = ctx.db.get(Patient, case.patient_id)
    tb = wording_port.teach_back(patient.language, slots_for(ctx.db, case), sms=patient.channel == "SMS")
    correct = p.teach_back_answer.strip() == str(tb["correct"])
    if not correct:
        case.teach_back_failures += 1
        if case.teach_back_first_pass is None:
            case.teach_back_first_pass = False
        ctx.log(EventType.TEACH_BACK_FAILED, payload={"failures": case.teach_back_failures})
        limit = int(engine.config.value("teach_back", "failures_before_call_task"))
        if case.teach_back_failures >= limit and open_task(ctx.db, case.id, "TEACH_BACK_CALL") is None:
            add_task(ctx.db, case, ctx.now, "TEACH_BACK_CALL", "call_the_patient", "coordinator",
                     default_owner(ctx.db, case, Role.COORDINATOR))
        add_message(ctx.db, case, ctx.now, "teach_back_simpler", tb["simpler"], language=patient.language,
                    channel=patient.channel, version="wording")
        if ctx.feedback is None:
            ctx.feedback = Feedback(code="TEACH_BACK_RETRY", message=tb["simpler"], template_id="teach_back_simpler")
        return
    if case.teach_back_first_pass is None:
        case.teach_back_first_pass = True
    case.patient_confidence = p.confidence
    before = ctx.move(State.ACKNOWLEDGED)
    begin_step(ctx.db, case, ctx.now)
    ctx.log(EventType.TEACH_BACK_PASSED, from_state=before, to_state=State.ACKNOWLEDGED.value,
            payload={"confidence": p.confidence, "failures_before_pass": case.teach_back_failures})


def do_choose_confirmation(ctx: Ctx, p: ChooseConfirmationPayload) -> None:
    ctx.case.confirmation_method = p.method.value
    ctx.log(EventType.CONFIRMATION_CHOSEN, payload={"method": p.method.value})


_SOURCE_ROLES = {
    ReadingSource.HOME_CUFF: {Role.PATIENT, Role.COORDINATOR},
    ReadingSource.CLINIC: {Role.COORDINATOR, Role.CLINICIAN},
    ReadingSource.ABPM: {Role.COORDINATOR, Role.CLINICIAN},
}


def do_add_reading(ctx: Ctx, p: AddReadingPayload) -> None:
    if p.systolic <= p.diastolic:
        raise ApiError(422, "INVALID_PAYLOAD", "systolic must be higher than diastolic")
    if p.taken_at.tzinfo is None:
        raise ApiError(422, "INVALID_PAYLOAD", "taken_at must include a timezone")
    if p.taken_at > ctx.now + timedelta(minutes=5):
        raise ApiError(422, "INVALID_PAYLOAD", "taken_at is in the future")
    if ctx.role not in _SOURCE_ROLES[p.source]:
        raise ApiError(403, "FORBIDDEN_SOURCE", f"A {ctx.role.value} cannot enter a {p.source.value} reading.")
    row = Reading(case_id=ctx.case.id, systolic=p.systolic, diastolic=p.diastolic, pulse=p.pulse, taken_at=p.taken_at,
                  source=p.source.value, entered_by_role=ctx.role.value, entered_by_user_id=ctx.user.id if ctx.user else None)
    ctx.db.add(row)
    ctx.db.flush()
    ctx.log(EventType.READING_ADDED, payload={"reading_id": row.id, "source": p.source.value,
                                              "systolic": p.systolic, "diastolic": p.diastolic})
    if engine.classify(p.systolic, p.diastolic) is Severity.SEVERE:
        ctx.case.severity = Severity.SEVERE.value
        flag_urgent(ctx.db, ctx.case, ctx.now, "SEVERE_READING", ctx.user)
        patient = ctx.db.get(Patient, ctx.case.patient_id)
        ctx.feedback = Feedback(code="SEVERE_READING", message=emergency_text(ctx.case.region, patient.language))


def do_review_confirmation(ctx: Ctx, p: ReviewConfirmationPayload) -> None:
    case = ctx.case
    cd = case_data(ctx.db, case)
    if p.outcome is ReviewOutcome.CONFIRMED:
        if cd.confirmation_status is None or cd.confirmation_status is ConfirmationStatus.INSUFFICIENT:
            raise ApiError(409, "INSUFFICIENT_READINGS", "There are not yet enough confirmation readings to review.")
        before = ctx.move(State.CONFIRMED)
        case.suggested_closure_type = None
        begin_step(ctx.db, case, ctx.now)
        ctx.log(EventType.CONFIRMATION_REVIEWED, from_state=before, to_state=State.CONFIRMED.value,
                payload={"outcome": "CONFIRMED", "engine_status": cd.confirmation_status.value}, reason=p.note)
        return
    # NOT_CONFIRMED: stays ACKNOWLEDGED, closure decision owned by the reviewing clinician. Never auto-closed.
    case.suggested_closure_type = ClosureEvidence.NOT_CONFIRMED.value
    begin_step(ctx.db, case, ctx.now, sync=False)
    case.owner_role, case.owner_user_id = Role.CLINICIAN.value, ctx.user.id
    ctx.log(EventType.CONFIRMATION_REVIEWED, payload={"outcome": "NOT_CONFIRMED", "engine_status": cd.confirmation_status.value if cd.confirmation_status else None},
            reason=p.note)


def _resolve_receiver(db: Session, p: ReferPayload, region: str) -> tuple[int | None, str | None]:
    if p.to_user_id is not None:
        target = db.get(User, p.to_user_id)
        if target is None or target.role != "clinician" or not target.active:
            raise ApiError(422, "INVALID_PAYLOAD", "to_user_id must be an active clinician")
        return target.id, p.to_service
    if not p.to_service:
        raise ApiError(422, "INVALID_PAYLOAD", "Give to_user_id or to_service")
    q = select(User).where(User.role == "clinician", User.active.is_(True), User.region == region, User.description.contains("hypertension"))
    target = db.scalars(q.order_by(User.id)).first()
    return (target.id if target else None), p.to_service


def do_refer(ctx: Ctx, p: ReferPayload) -> None:
    to_id, service = _resolve_receiver(ctx.db, p, ctx.case.region)
    ref = Referral(case_id=ctx.case.id, from_user_id=ctx.user.id, to_user_id=to_id, to_service=service, reason=p.reason,
                   status=ReferralStatus.PENDING.value, created_at=ctx.now)
    ctx.db.add(ref)
    ctx.case.referral_status = ReferralStatus.PENDING.value
    ctx.db.flush()
    before = ctx.move(State.REFERRED)
    begin_step(ctx.db, ctx.case, ctx.now)
    send_template(ctx.db, ctx.case, ctx.now, "referral_sent")
    ctx.log(EventType.REFERRAL_SENT, from_state=before, to_state=State.REFERRED.value,
            payload={"to_user_id": to_id, "to_service": service}, reason=p.reason)


def do_accept_referral(ctx: Ctx, p: BaseModel) -> None:
    ref = _active_referral(ctx)
    ref.status, ref.decided_at = ReferralStatus.ACCEPTED.value, ctx.now
    ctx.case.referral_status = ReferralStatus.ACCEPTED.value
    begin_step(ctx.db, ctx.case, ctx.now)  # booking sub-step, owned by the coordinator
    send_template(ctx.db, ctx.case, ctx.now, "referral_accepted")
    ctx.log(EventType.REFERRAL_ACCEPTED, payload={"referral_id": ref.id})


def do_reject_referral(ctx: Ctx, p: ReasonPayload) -> None:
    ref = _active_referral(ctx)
    ref.status, ref.rejection_reason, ref.decided_at = ReferralStatus.REJECTED.value, p.reason, ctx.now
    ctx.case.referral_status = ReferralStatus.REJECTED.value
    before = ctx.move(State.CONFIRMED)
    begin_step(ctx.db, ctx.case, ctx.now, sync=False)
    ctx.case.owner_role, ctx.case.owner_user_id = Role.COORDINATOR.value, None
    ctx.log(EventType.REFERRAL_REJECTED, from_state=before, to_state=State.CONFIRMED.value,
            payload={"referral_id": ref.id}, reason=p.reason)


def _active_referral(ctx: Ctx) -> Referral:
    ref = ctx.db.scalars(select(Referral).where(Referral.case_id == ctx.case.id).order_by(Referral.id.desc())).first()
    if ref is None:
        raise ApiError(409, "NO_PENDING_REFERRAL", "There is no referral on this case.")
    return ref


def do_assign_owner(ctx: Ctx, p: AssignOwnerPayload) -> None:
    target = ctx.db.get(User, p.user_id)
    if target is None or not target.active or target.role not in ("coordinator", "clinician"):
        raise ApiError(422, "INVALID_PAYLOAD", "user_id must be an active coordinator or clinician")
    old = ctx.case.owner_user_id
    ctx.case.owner_user_id, ctx.case.owner_role = target.id, target.role
    if ctx.case.referral_status == ReferralStatus.REJECTED.value:
        ctx.case.step_started_at = ctx.now  # a reassigned case gets a fresh due date
    ctx.log(EventType.OWNER_CHANGED, payload={"from_user_id": old, "to_user_id": target.id})


def do_book_appointment(ctx: Ctx, p: BookAppointmentPayload) -> None:
    slot = ctx.db.get(Slot, p.slot_id)
    if slot is None or slot.booked or slot.region != ctx.case.region or slot.starts_at <= ctx.now:
        raise ApiError(409, "SLOT_UNAVAILABLE", "That time is not available. Please choose another.")
    slot.booked = True
    ctx.db.add(Appointment(case_id=ctx.case.id, slot_id=slot.id, starts_at=slot.starts_at, provider_name=slot.provider_name,
                           location=slot.location, created_at=ctx.now))
    ctx.db.flush()
    before = ctx.move(State.APPOINTMENT_BOOKED)
    begin_step(ctx.db, ctx.case, ctx.now)
    send_template(ctx.db, ctx.case, ctx.now, "appointment_booked")
    ctx.log(EventType.APPOINTMENT_BOOKED, from_state=before, to_state=State.APPOINTMENT_BOOKED.value,
            payload={"slot_id": slot.id, "starts_at": slot.starts_at.isoformat()})


def do_record_visit(ctx: Ctx, p: RecordVisitPayload) -> None:
    case = ctx.case
    appt = ctx.db.scalars(select(Appointment).where(Appointment.case_id == case.id).order_by(Appointment.id.desc())).first()
    if appt:
        appt.status = "ATTENDED"
    case.visit_outcome = p.outcome.value
    before = ctx.move(State.IN_CARE)
    begin_step(ctx.db, case, ctx.now, sync=False)
    case.owner_role, case.owner_user_id = Role.CLINICIAN.value, ctx.user.id
    start_plan(ctx.db, case, ctx.now)
    ctx.log(EventType.VISIT_RECORDED, from_state=before, to_state=State.IN_CARE.value,
            payload={"outcome": p.outcome.value}, reason=p.note)


def do_plan_checkin(ctx: Ctx, p: PlanCheckinPayload) -> None:
    week = open_week(ctx.db, ctx.case.id)
    if week is None:
        raise ApiError(409, "NO_ACTIVE_WEEK", "There is no open plan week to check in.")
    result = record_checkin(ctx.db, ctx.case, week, p.status, ctx.now, barrier=p.barrier.value if p.barrier else None,
                            accept_larger=p.accept_larger, actor=ctx.user)
    d = result["decision"]
    patient = ctx.db.get(Patient, ctx.case.patient_id)
    texts = []
    for key in d.message_keys:
        if key == "weekly_action":
            continue
        from .core import slots_for
        rendered = wording_port.render(key, patient.language, slots_for(ctx.db, ctx.case, {"action": result["texts"], "action_text": result["texts"]}), patient.channel)
        texts.append(rendered.text)
        add_message(ctx.db, ctx.case, ctx.now, key, rendered.text, language=patient.language, channel=patient.channel,
                    version=rendered.template_version)
    code = "PLAN_SMALLER" if d.shrunk else ("PLAN_LARGER_OFFERED" if d.offer_larger else "PLAN_NEXT")
    ctx.feedback = Feedback(code=code, message=" ".join(texts) or result["texts"])


def do_escalate(ctx: Ctx, p: ReasonPayload) -> None:
    ctx.case.escalation_level = 2
    ctx.log(EventType.ESCALATED, payload={"level": 2, "manual": True,
                                          "target": "on_call_clinician" if ctx.case.severity == "SEVERE" else "coordinator_lead"}, reason=p.reason)


def do_close(ctx: Ctx, p: ClosePayload) -> None:
    v = engine.validate_closure(ctx.role, p.evidence_type.value if p.evidence_type else None, p.evidence_ref, p.decision_note)
    if not v.ok:
        raise ApiError(v.status, v.code, v.message)
    case = ctx.case
    case.state_before_close = case.state
    before = ctx.move(State.CLOSED)
    case.closed_at, case.closed_by_user_id = ctx.now, ctx.user.id
    case.closure_evidence_type = p.evidence_type.value
    case.closure_evidence_ref = (p.evidence_ref or "").strip() or None
    case.closure_decision_note = (p.decision_note or "").strip() or None
    case.owner_user_id = None
    if case.urgent and case.urgent_review_done_at is None:
        case.urgent_review_done_at = ctx.now
    case.urgent = False
    for t in ("URGENT_REVIEW", "COORDINATOR_CALL", "CLINICIAN_DECISION", "TEACH_BACK_CALL", "PLAN_CALL_OFFER"):
        complete_tasks(ctx.db, case.id, t, ctx.now)
    ctx.log(EventType.CASE_CLOSED, from_state=before, to_state=State.CLOSED.value,
            payload={"evidence_type": p.evidence_type.value, "evidence_ref": case.closure_evidence_ref},
            reason=case.closure_decision_note)


def do_reopen(ctx: Ctx, p: ReasonPayload) -> None:
    v = engine.validate_reopen(ctx.role, p.reason)
    if not v.ok:
        raise ApiError(v.status, v.code, v.message)
    case = ctx.case
    back = State(case.state_before_close or State.ACKNOWLEDGED.value)
    before = ctx.move(back)
    case.closed_at = case.closed_by_user_id = case.closure_evidence_type = None
    case.closure_evidence_ref = case.closure_decision_note = None
    case.suggested_closure_type = None
    begin_step(ctx.db, case, ctx.now)  # fresh due date
    ctx.log(EventType.CASE_REOPENED, from_state=before, to_state=back.value, reason=p.reason)


def do_update_consent(ctx: Ctx, p: ConsentPayload) -> None:
    patient = ctx.db.get(Patient, ctx.case.patient_id)
    if p.purpose.value == "messaging_channel" and p.channel is None:
        raise ApiError(422, "INVALID_PAYLOAD", "channel is required for messaging_channel")
    channel = p.channel.value if p.purpose.value == "messaging_channel" else None
    q = select(Consent).where(Consent.patient_id == patient.id, Consent.purpose == p.purpose.value, Consent.channel == channel)
    row = ctx.db.scalars(q).first()
    if row is None:
        row = Consent(patient_id=patient.id, purpose=p.purpose.value, channel=channel, granted=p.granted)
        ctx.db.add(row)
    row.granted = p.granted
    if p.granted:
        row.granted_at = ctx.now
    else:
        row.withdrawn_at = ctx.now
    ctx.log(EventType.CONSENT_CHANGED, payload={"purpose": p.purpose.value, "channel": channel, "granted": p.granted})


def do_complete_urgent_review(ctx: Ctx, p: UrgentReviewPayload) -> None:
    case = ctx.case
    case.urgent_review_done_at = ctx.now
    case.urgent = False
    complete_tasks(ctx.db, case.id, "URGENT_REVIEW", ctx.now)
    ctx.log(EventType.URGENT_REVIEW_COMPLETED, reason=p.note)


HANDLERS: dict[Action, Callable[[Ctx, Any], None]] = {
    Action.NOTIFY: do_notify,
    Action.ACKNOWLEDGE: do_acknowledge,
    Action.CHOOSE_CONFIRMATION: do_choose_confirmation,
    Action.ADD_READING: do_add_reading,
    Action.REVIEW_CONFIRMATION: do_review_confirmation,
    Action.REFER: do_refer,
    Action.ACCEPT_REFERRAL: do_accept_referral,
    Action.REJECT_REFERRAL: do_reject_referral,
    Action.ASSIGN_OWNER: do_assign_owner,
    Action.BOOK_APPOINTMENT: do_book_appointment,
    Action.RECORD_VISIT: do_record_visit,
    Action.PLAN_CHECKIN: do_plan_checkin,
    Action.ESCALATE: do_escalate,
    Action.CLOSE: do_close,
    Action.REOPEN: do_reopen,
    Action.UPDATE_CONSENT: do_update_consent,
    Action.COMPLETE_URGENT_REVIEW: do_complete_urgent_review,
}
