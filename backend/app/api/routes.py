"""HTTP routes for SPEC section 6 (dashboard, demo and FHIR routes live in their own modules)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Case, EConsult, MessageDraft, Patient, Slot, User
from app.demo import clock
from app.engine.types import Action, EventType, Role, State

from . import auth, i18n, message_slots, projection, schemas as S, wording_port
from .actions_impl import perform
from .constants import APP_NAME
from .core import (
    STAFF, ApiError, Prepared, case_data, log, messages_of, neutral_slots, refresh_case, send_message, split_name, user_name,
)
from .deps import anyone_but_patient, can_view, clinician_only, current_user, get_db, load_case, patient_only, role_of, staff
from .demo_mode import demo_mode, require_demo
from .intake import get_or_create_patient, handle_reply, open_case
from .regions import REGIONS

router = APIRouter(prefix="/api")
_FIXED_REPLIES = {"reply_received", "call_requested", "reply_not_understood", "stop_confirmed"}
ERR = {403: {"model": S.ErrorResponse}, 404: {"model": S.ErrorResponse}, 409: {"model": S.ErrorResponse}}


def user_out(u: User) -> S.UserOut:
    display, title = split_name(u.name, u.role)
    return S.UserOut(id=u.id, persona=u.persona_key, name=u.name, display_name=display, role_title=title, role=u.role,
                     display_names=S.I18nText(**i18n.person_names(u.name)), role_titles=S.I18nText(**i18n.person_roles(u.name, u.role)),
                     organisation_i18n=S.I18nText(**i18n.place(u.organisation)),
                     region=u.region, organisation=u.organisation, language=u.language, patient_id=u.patient_id,
                     description=u.description)


# ------------------------------------------------------------------ public and auth


@router.get("/health", response_model=S.HealthOut, tags=["system"])
def health(db: Session = Depends(get_db)):
    return S.HealthOut(status="ok", app=APP_NAME, now=clock.now(db))


@router.get("/personas", response_model=list[S.PersonaInfo], tags=["auth"])
def personas(db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.persona_key.is_not(None)).order_by(User.id))
    out = []
    for u in rows:
        display, title = split_name(u.name, u.role)
        out.append(S.PersonaInfo(persona=u.persona_key, name=u.name, display_name=display, role_title=title, role=u.role,
                                 display_names=S.I18nText(**i18n.person_names(u.name)),
                                 role_titles=S.I18nText(**i18n.person_roles(u.name, u.role)),
                                 region=u.region, description=u.description, listed=u.persona_key != "specialist_yde"))
    return out


@router.post("/auth/guest", response_model=S.AuthResponse, tags=["auth"])
def guest(req: S.GuestRequest, _demo: None = Depends(require_demo), db: Session = Depends(get_db)):
    """Guest sign-in is a demo control: with DEMO_MODE off it answers 403 DEMO_MODE_OFF."""
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
    entries = [S.ConfigEntryOut(section=e.section, key=e.key, value=e.value, unit=e.unit, basis=e.basis, status=e.status,
                                label_i18n=S.I18nText(**i18n.tri(e.label_i18n, e.key)), basis_i18n=S.I18nText(**i18n.tri(e.basis_i18n, e.basis)),
                                unit_i18n=S.I18nText(**i18n.tri(e.unit_i18n, e.unit)))
               for e in engine.config.all_entries()]
    regions = [S.RegionConfig(region=k, name=v["name"], name_i18n=S.I18nText(**i18n.region_names(k)), default_language=v["default_language"], languages=v["languages"],
                              emergency_text=v["emergency_text"], emergency_number=v["emergency_number"], timezone=v["timezone"])
               for k, v in REGIONS.items()]
    return S.ConfigOut(
        app_name=APP_NAME, demo_mode=demo_mode(),
        notice="Every threshold and service level is a placeholder pending clinician sign-off. None is clinically validated.",
        entries=entries, closure_evidence_types=list(engine.ClosureEvidence),
        closure_evidence_labels=[S.ClosureEvidenceLabel(code=c, label_i18n=S.I18nText(**i18n.closure_label(c.value)))
                                 for c in engine.ClosureEvidence],
        notice_i18n=S.I18nText(**i18n.config_notice()), rules_i18n=[S.I18nText(**r) for r in i18n.config_rules()], templates=wording_port.template_catalogue(),
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
def my_case(language: S.Language | None = None, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    """The patient's own case. `language` selects the language of the structured teach-back and the plan texts."""
    case = _own_case(db, user)
    now = clock.now(db)
    refresh_case(db, case, now)
    db.commit()
    return projection.case_detail(db, case, user, Role.PATIENT, now, patient_view=True, language=language.value if language else None)


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
    """Simulated cover lines. Always tagged simulated, in every language."""
    def out(kind: str, text: str, covered, copay_value, price, currency, **params) -> S.CoverOut:
        return S.CoverOut(covered=covered, copay=copay_value, estimated_price=price, currency=currency, label=text,
                          label_i18n=S.I18nText(**i18n.cover_label(kind, **params)),
                          simulated_label_i18n=S.I18nText(**i18n.simulated_label()))

    if patient.region == "AUH":
        if patient.insurance == "THIQA":
            return out("thiqa", "Covered by Thiqa (simulated), no co-payment", True, 0, None, "AED")
        if patient.insurance == "BASIC":
            return out("basic", "Covered by basic plan (simulated), co-payment AED 20", True, 20, None, "AED", copay=20)
        return out("self_pay", "Self-pay estimate (simulated)", False, None, 250, "AED")
    return out("estimate", "Estimated price (simulated)", None, None, 5000, "XAF")


@router.get("/cases/{case_id}/slots", response_model=list[S.SlotOut], tags=["cases"], responses=ERR)
def slots(case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    now = clock.now(db)
    patient = db.get(Patient, case.patient_id)
    q = select(Slot).where(Slot.region == case.region, Slot.booked.is_(False), Slot.starts_at > now).order_by(Slot.starts_at).limit(12)
    return [S.SlotOut(id=s.id, starts_at=s.starts_at, provider_name=s.provider_name, location=s.location, cover=cover_for(patient, s),
                      provider_name_i18n=S.I18nText(**i18n.person_names(s.provider_name)),
                      provider_person=projection.person_from_name(s.provider_name, "clinician"),
                      location_i18n=S.I18nText(**i18n.place(s.location)),
                      label_i18n=projection.appointment_label(s.starts_at, s.provider_name, s.location, case.region))
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


@router.post("/cases/{case_id}/messages/draft", response_model=S.DraftOut, tags=["messages"], responses=ERR)
def draft_message(case_id: int, req: S.DraftRequest, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Render an approved template into a draft stored on the server. Optional re-wording (`tone`) is validated here."""
    case = load_case(db, user, case_id)
    patient = db.get(Patient, case.patient_id)
    if req.template_id in _FIXED_REPLIES or not wording_port.known_template(req.template_id):
        raise ApiError(422, "UNKNOWN_TEMPLATE", "Only approved templates can be drafted.")
    channel = (req.channel or S.Channel(patient.channel)).value
    lang = req.language.value
    neutral = neutral_slots(db, case, req.template_id)
    slots = message_slots.localize(neutral, lang, case.region)
    try:
        base = wording_port.render(req.template_id, lang, slots, channel, strict=True)
    except wording_port.WordingUnavailable as exc:
        raise ApiError(422, "TEMPLATE_UNAVAILABLE", f"The template cannot be rendered with this case's data: {exc}") from exc
    limit = wording_port.channel_limit(base.template_id, channel, lang)
    out = wording_port.reword(base.text, lang, req.tone, slots, base, max_length=limit) if req.tone else base
    validation = out.validation or {"passed": True, "failed_reason": None, "checks": [], "provider": "none"}
    row = MessageDraft(case_id=case.id, template_id=req.template_id, template_version=base.template_version, language=lang,
                       channel=channel, slots=neutral, text=out.text, source=out.source, tone=req.tone, validation=validation,
                       created_by_user_id=user.id, created_at=clock.now(db))
    db.add(row)
    db.commit()
    return S.DraftOut(id=row.id, channel=S.Channel(channel), text=row.text, source=row.source, template_id=row.template_id,
                      template_version=row.template_version, language=req.language, validation=row.validation)


@router.post("/cases/{case_id}/messages/send", response_model=S.SendResponse, tags=["messages"], responses=ERR)
def send_message_route(case_id: int, req: S.SendRequest, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Send a stored draft. The server re-renders the template, re-runs the validator for an AI re-worded draft and
    requires explicit approval by the signed-in staff member for it. The client cannot supply text or a source."""
    case = load_case(db, user, case_id)
    draft = db.get(MessageDraft, req.draft_id)
    if draft is None or draft.case_id != case.id:
        raise ApiError(404, "DRAFT_NOT_FOUND", "No such draft for this case. Create a draft first.")
    if draft.sent_message_id is not None:
        raise ApiError(409, "ALREADY_SENT", "This draft has already been sent.")
    slots = message_slots.localize(draft.slots, draft.language, case.region)  # the slots stored with the draft, not today's
    try:
        base = wording_port.render(draft.template_id, draft.language, slots, draft.channel, strict=True)
    except wording_port.WordingUnavailable as exc:
        raise ApiError(422, "TEMPLATE_UNAVAILABLE", f"The template cannot be rendered: {exc}") from exc
    if draft.source == S.MessageSource.AI_REWORDED.value:
        if not req.approve:
            raise ApiError(409, "APPROVAL_REQUIRED", "An AI re-worded draft must be approved by a staff member before it is sent.")
        try:
            validation = wording_port.validate_text(base.text, draft.text, draft.language, slots,
                                                    wording_port.channel_limit(base.template_id, draft.channel, draft.language))
        except wording_port.WordingUnavailable as exc:
            raise ApiError(422, "VALIDATION_UNAVAILABLE", str(exc)) from exc
        if not validation["passed"]:
            raise ApiError(422, "VALIDATION_FAILED", f"The re-worded text failed validation: {validation['failed_reason']}")
        validation["provider"] = (draft.validation or {}).get("provider")
        text, source, approver = draft.text, S.MessageSource.AI_REWORDED.value, user
    else:
        text, source, approver = base.text, S.MessageSource.TEMPLATE.value, (user if req.approve else None)
        validation = draft.validation
    now = clock.now(db)
    prepared = Prepared(text=text, version=base.template_version, source=source, neutral=draft.slots, validation=validation,
                        draft_id=draft.id, approved_by=approver)
    msg = send_message(db, case, now, draft.template_id, kind=STAFF, sender=user, language=draft.language, channel=draft.channel,
                       prepared=prepared)
    if msg is None:
        db.commit()  # keep the suppression event and the coordinator task
        raise ApiError(409, "CONSENT_WITHDRAWN", "The patient has withdrawn permission for this messaging channel or for care coordination. "
                       "Nothing was sent; a coordinator task asks for another agreed route.")
    db.flush()
    draft.sent_message_id = msg.id
    db.commit()
    return S.SendResponse(message=projection._message_out(db, msg))


@router.get("/my/messages", response_model=list[S.MessageOut], tags=["patient"])
def my_messages(language: S.Language | None = None, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    """The thread. With `language`, template-based outgoing messages are re-rendered in that language (patient language switch).

    The re-render uses the slots stored with each message, so its reading and dates are the ones from when it was created.
    A message stored before slots were kept, or one that cannot render in the language, keeps its stored text.
    """
    case = _own_case(db, user)
    rows = messages_of(db, case.id)
    out = projection.message_list(db, case.id)
    if language is not None:
        for m, row in zip(out, rows):
            if row.direction == "OUT" and row.template_id and row.source == S.MessageSource.TEMPLATE.value and row.slots is not None:
                r = wording_port.render(row.template_id, language.value, message_slots.localize(row.slots, language.value, case.region), row.channel)
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
def intake(req: S.IntakeRequest, _demo: None = Depends(require_demo), user: User = Depends(staff), db: Session = Depends(get_db)):
    """Demo control: with DEMO_MODE off this route answers 403 DEMO_MODE_OFF."""
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
