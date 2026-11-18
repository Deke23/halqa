"""HTTP routes for SPEC section 6 (dashboard, demo and FHIR routes live in their own modules)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Case, EConsult, Patient, Slot, User
from app.demo import clock
from app.engine.types import Action, EventType, Role, State

from . import auth, projection, schemas as S, wording_port
from .actions_impl import perform
from .constants import APP_NAME
from .core import ApiError, add_message, case_data, log, messages_of, refresh_case, user_name
from .deps import anyone_but_patient, can_view, clinician_only, current_user, get_db, load_case, patient_only, role_of, staff
from .intake import get_or_create_patient, handle_reply, open_case
from .regions import REGIONS

router = APIRouter(prefix="/api")
_INDEX_READING_TEMPLATES = {"result_raised", "result_severe", "teach_back_question", "teach_back_simpler"}
ERR = {403: {"model": S.ErrorResponse}, 404: {"model": S.ErrorResponse}, 409: {"model": S.ErrorResponse}}


def user_out(u: User) -> S.UserOut:
    return S.UserOut(id=u.id, persona=u.persona_key, name=u.name, role=u.role, region=u.region, organisation=u.organisation,
                     language=u.language, patient_id=u.patient_id, description=u.description)


# ------------------------------------------------------------------ public and auth


@router.get("/health", response_model=S.HealthOut, tags=["system"])
def health(db: Session = Depends(get_db)):
    return S.HealthOut(status="ok", app=APP_NAME, now=clock.now(db))


@router.get("/personas", response_model=list[S.PersonaInfo], tags=["auth"])
def personas(db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.persona_key.is_not(None)).order_by(User.id))
    return [S.PersonaInfo(persona=u.persona_key, name=u.name, role=u.role, region=u.region, description=u.description)
            for u in rows if u.persona_key not in ("clinician_yde", "specialist_yde")]


@router.post("/auth/guest", response_model=S.AuthResponse, tags=["auth"])
def guest(req: S.GuestRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.persona_key == req.persona.value)).first()
    if user is None:
        raise ApiError(404, "PERSONA_NOT_FOUND", "That persona is not seeded. Reset the demo data.")
    return S.AuthResponse(token=auth.issue(user.id, user.persona_key, user.role), user=user_out(user))


@router.get("/me", response_model=S.UserOut, tags=["auth"])
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/users", response_model=list[S.UserOut], tags=["auth"], summary="Staff directory for owner assignment and referral")
def users(role: S.RoleName | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    q = select(User).where(User.role.in_(["coordinator", "clinician"]), User.active.is_(True))
    if role:
        q = q.where(User.role == role.value)
    return [user_out(u) for u in db.scalars(q.order_by(User.id))]


@router.get("/config", response_model=S.ConfigOut, tags=["system"])
def config():
    entries = [S.ConfigEntryOut(section=e.section, key=e.key, value=e.value, unit=e.unit, basis=e.basis, status=e.status)
               for e in engine.config.all_entries()]
    regions = [S.RegionConfig(region=k, name=v["name"], default_language=v["default_language"], languages=v["languages"],
                              emergency_text=v["emergency_text"], emergency_number=v["emergency_number"])
               for k, v in REGIONS.items()]
    return S.ConfigOut(
        app_name=APP_NAME,
        notice="Every threshold and service level is a placeholder pending clinician sign-off. None is clinically validated.",
        entries=entries, closure_evidence_types=list(engine.ClosureEvidence), templates=wording_port.template_catalogue(),
        languages=list(S.Language), regions=regions,
        rules=[
            "Rules decide routing, urgency, ownership, SLA and closure. AI only drafts wording and never takes part in those decisions.",
            "Only a clinician can close a case, and only with an evidence type plus an evidence reference or a decision note.",
            "Blood pressure values come only from a validated cuff or ambulatory monitor. Wearable data is never used as a blood pressure value.",
            "The dashboard is aggregate only and hides any cell with fewer than 5 people.",
        ],
    )


# ------------------------------------------------------------------ cases


def _build_list(db: Session, user: User, queue: S.QueueName, region: S.Region | None) -> S.CaseList:
    now = clock.now(db)
    rows: list[tuple] = []
    for case in db.scalars(select(Case).order_by(Case.id)):
        if region and case.region != region.value:
            continue
        if not can_view(db, user, case):
            continue
        ev = refresh_case(db, case, now)
        cd = case_data(db, case)
        ev = ev or engine.evaluate(cd, now)
        if engine.queues.in_queue(queue.value, cd, ev, user.id):
            rows.append((engine.queues.sort_key(cd, ev), case, ev, cd))
    db.commit()
    rows.sort(key=lambda r: (r[0], r[1].id))
    cases = [projection.summary_of(db, c, ev, cd) for _, c, ev, cd in rows]
    return S.CaseList(queue=queue, total=len(cases), cases=cases)


@router.get("/cases", response_model=S.CaseList, tags=["cases"], responses=ERR)
def list_cases(queue: S.QueueName = S.QueueName.ALL, region: S.Region | None = None,
               user: User = Depends(staff), db: Session = Depends(get_db)):
    return _build_list(db, user, queue, region)


@router.get("/cases/{case_id}", response_model=S.CaseDetail, tags=["cases"], responses=ERR)
def get_case(case_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    now = clock.now(db)
    refresh_case(db, case, now)
    log(db, case, now, EventType.CASE_VIEWED, user, payload={"view": "detail"})
    db.commit()
    return projection.case_detail(db, case, user, role_of(user), now)


def _own_case(db: Session, user: User) -> Case:
    case = db.scalars(select(Case).where(Case.patient_id == user.patient_id).order_by(Case.id.desc())).first()
    if case is None:
        raise ApiError(404, "CASE_NOT_FOUND", "You have no open follow-up.")
    return case


@router.get("/my/case", response_model=S.CaseDetail, tags=["patient"], responses=ERR)
def my_case(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    case = _own_case(db, user)
    now = clock.now(db)
    refresh_case(db, case, now)
    db.commit()
    return projection.case_detail(db, case, user, Role.PATIENT, now, patient_view=True)


@router.post("/cases/{case_id}/actions", response_model=S.CaseDetail, tags=["cases"],
             responses={**ERR, 422: {"model": S.ErrorResponse}},
             summary="The only way to change case state")
def post_action(case_id: int, req: S.ActionRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    now = clock.now(db)
    role = role_of(user)
    refresh_case(db, case, now)
    try:
        feedback = perform(db, case, user, role, req.action, req.payload, now)
        refresh_case(db, case, now)
        db.commit()
    except Exception:
        db.rollback()
        raise
    patient_view = role is Role.PATIENT
    detail = projection.case_detail(db, case, user, role, now, patient_view=patient_view)
    detail.feedback = feedback
    return detail


# ------------------------------------------------------------------ slots


def cover_for(patient: Patient, slot: Slot) -> S.CoverOut:
    """Simulated cover lines. Always tagged simulated."""
    if patient.region == "AUH":
        if patient.insurance == "THIQA":
            return S.CoverOut(covered=True, copay=0, estimated_price=None, currency="AED", label="Covered by Thiqa (simulated), no co-payment")
        if patient.insurance == "BASIC":
            return S.CoverOut(covered=True, copay=20, estimated_price=None, currency="AED", label="Covered by basic plan (simulated), co-payment AED 20")
        return S.CoverOut(covered=False, copay=None, estimated_price=250, currency="AED", label="Self-pay estimate (simulated)")
    return S.CoverOut(covered=None, copay=None, estimated_price=5000, currency="XAF", label="Estimated price (simulated)")


@router.get("/cases/{case_id}/slots", response_model=list[S.SlotOut], tags=["cases"], responses=ERR)
def slots(case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    now = clock.now(db)
    patient = db.get(Patient, case.patient_id)
    q = select(Slot).where(Slot.region == case.region, Slot.booked.is_(False), Slot.starts_at > now).order_by(Slot.starts_at).limit(12)
    return [S.SlotOut(id=s.id, starts_at=s.starts_at, provider_name=s.provider_name, location=s.location, cover=cover_for(patient, s))
            for s in db.scalars(q)]


# ------------------------------------------------------------------ e-consults


@router.post("/cases/{case_id}/econsults", response_model=S.EConsultOut, tags=["econsults"], responses=ERR)
def ask_econsult(case_id: int, req: S.EConsultCreate, user: User = Depends(clinician_only), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    target = db.get(User, req.to_user_id)
    if target is None or target.role != "clinician" or not target.active or target.id == user.id:
        raise ApiError(422, "INVALID_PAYLOAD", "to_user_id must be another active clinician")
    now = clock.now(db)
    row = EConsult(case_id=case.id, from_user_id=user.id, to_user_id=target.id, question=req.question, created_at=now)
    db.add(row)
    db.flush()
    log(db, case, now, EventType.ECONSULT_ASKED, user, payload={"econsult_id": row.id, "to_user_id": target.id})
    db.commit()
    return projection.econsult_out(db, row)


@router.post("/econsults/{econsult_id}/reply", response_model=S.EConsultOut, tags=["econsults"], responses=ERR)
def reply_econsult(econsult_id: int, req: S.EConsultReply, user: User = Depends(clinician_only), db: Session = Depends(get_db)):
    row = db.get(EConsult, econsult_id)
    if row is None:
        raise ApiError(404, "ECONSULT_NOT_FOUND", "No such e-consult.")
    if row.to_user_id != user.id:
        raise ApiError(403, "NOT_RECIPIENT", "Only the clinician who was asked can reply.")
    if row.status != "OPEN":
        raise ApiError(409, "ALREADY_ANSWERED", "This e-consult has already been answered.")
    now = clock.now(db)
    row.answer, row.status, row.answered_at = req.answer, "ANSWERED", now
    case = db.get(Case, row.case_id)
    log(db, case, now, EventType.ECONSULT_ANSWERED, user, payload={"econsult_id": row.id})
    db.commit()
    return projection.econsult_out(db, row)


@router.get("/econsults", response_model=list[S.EConsultOut], tags=["econsults"], summary="E-consults asked by or to me")
def my_econsults(user: User = Depends(clinician_only), db: Session = Depends(get_db)):
    q = select(EConsult).where((EConsult.to_user_id == user.id) | (EConsult.from_user_id == user.id)).order_by(EConsult.id.desc())
    return [projection.econsult_out(db, e) for e in db.scalars(q)]


# ------------------------------------------------------------------ messages


def _slot_values(db: Session, case: Case) -> dict:
    from .core import slots_for
    return slots_for(db, case)


@router.post("/cases/{case_id}/messages/draft", response_model=S.DraftOut, tags=["messages"], responses=ERR)
def draft_message(case_id: int, req: S.DraftRequest, user: User = Depends(staff), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    slots = _slot_values(db, case)
    base = wording_port.render(req.template_id, req.language.value, slots)
    out = wording_port.reword(base.text, req.language.value, req.tone, slots, base) if req.tone else base
    return S.DraftOut(text=out.text, source=out.source, template_id=out.template_id, template_version=out.template_version,
                      language=req.language, validation=out.validation)


@router.post("/cases/{case_id}/messages/send", response_model=S.SendResponse, tags=["messages"], responses=ERR)
def send_message(case_id: int, req: S.SendRequest, user: User = Depends(staff), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    d = req.draft
    if d.source == S.MessageSource.AI_REWORDED and not req.approve:
        raise ApiError(409, "APPROVAL_REQUIRED", "An AI re-worded draft must be approved by staff before it is sent.")
    if not d.text.strip():
        raise ApiError(422, "INVALID_PAYLOAD", "The message is empty.")
    patient = db.get(Patient, case.patient_id)
    channel = (req.channel or S.Channel(patient.channel)).value
    from .core import consent_granted
    if not consent_granted(db, patient.id, "messaging_channel", channel):
        raise ApiError(409, "CONSENT_WITHDRAWN", "The patient has withdrawn permission for this messaging channel.")
    now = clock.now(db)
    approver = user if (req.approve or d.source == S.MessageSource.AI_REWORDED) else None
    msg = add_message(db, case, now, d.template_id, d.text, language=d.language.value, channel=channel, sender=user,
                      source=d.source.value, version=d.template_version, approved_by=approver)
    db.flush()
    log(db, case, now, EventType.MESSAGE_SENT, user, payload={
        "template_id": d.template_id, "source": d.source.value, "channel": channel,
        "approved_by_user_id": approver.id if approver else None, "validation": d.validation})
    db.commit()
    return S.SendResponse(message=projection._message_out(db, msg))


@router.get("/my/messages", response_model=list[S.MessageOut], tags=["patient"])
def my_messages(language: S.Language | None = None, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    """The thread. With `language`, template-based outgoing messages are re-rendered in that language (patient language switch)."""
    case = _own_case(db, user)
    out = projection.message_list(db, case.id)
    if language is not None:
        from .core import slots_for
        slots = slots_for(db, case, language=language.value)
        # Result and teach-back messages quote the reading that opened the case, not the latest home reading.
        index_slots = {**slots, "systolic": case.index_systolic, "diastolic": case.index_diastolic,
                       "reading": f"{case.index_systolic}/{case.index_diastolic}"}
        for m in out:
            if m.direction == "OUT" and m.template_id and m.source == S.MessageSource.TEMPLATE:
                about_result = m.template_id.removesuffix("_sms") in _INDEX_READING_TEMPLATES
                r = wording_port.render(m.template_id, language.value, index_slots if about_result else slots, m.channel)
                # A template that could not render in this language falls back to built-in English. Keep the stored text then.
                if r.text and r.language == language.value:
                    m.text, m.language = r.text, language
    return out


@router.post("/my/messages/reply", response_model=list[S.MessageOut], tags=["patient"])
def my_reply(req: S.ReplyRequest, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    case = _own_case(db, user)
    now = clock.now(db)
    patient = db.get(Patient, case.patient_id)
    try:
        handle_reply(db, case, patient, req.text, now)
        refresh_case(db, case, now)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return projection.message_list(db, case.id)


# ------------------------------------------------------------------ intake


@router.post("/intake/result", response_model=S.IntakeResponse, tags=["intake"], responses=ERR,
             summary="Simulated source feed. Opens a case when the reading is actionable")
def intake(req: S.IntakeRequest, user: User = Depends(staff), db: Session = Depends(get_db)):
    now = clock.now(db)
    patient = get_or_create_patient(db, req, now)
    rows = [(r.systolic, r.diastolic, r.pulse, r.taken_at or now) for r in req.readings]
    existing = db.scalars(select(Case).where(Case.patient_id == patient.id, Case.state != State.CLOSED.value)).first()
    if existing:
        severe = any(engine.classify(s, d) is engine.Severity.SEVERE for s, d, _, _ in rows)
        if severe:
            from .core import flag_urgent
            existing.severity = engine.Severity.SEVERE.value
            flag_urgent(db, existing, now, "SEVERE_READING", user)
        db.commit()
        return S.IntakeResponse(opened=False, case_id=existing.id, severity=existing.severity, reason="OPEN_CASE_EXISTS")
    case = open_case(db, patient, rows, req.source_system.value, now)
    if case is None:
        db.commit()
        return S.IntakeResponse(opened=False, case_id=None, severity=None, reason="NOT_ACTIONABLE")
    db.commit()
    return S.IntakeResponse(opened=True, case_id=case.id, severity=case.severity, reason="CASE_OPENED")
