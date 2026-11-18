"""Opening cases from a simulated screening or clinic feed, and the phone-thread reply parser.

Safety property: replies are parsed by fixed keywords and one numeric pattern only. No model
reads a patient's text.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Case, CaseEvent, Consent, Patient, Reading, User
from app.engine.types import Action, EventType, ReadingSource, Role, Severity, State

from . import schemas as S
from .actions_impl import perform
from .core import (
    ApiError, _active, add_message, add_task, default_owner, flag_urgent, log, open_task, open_week, readings_of, send_template,
)
from . import wording_port
from .regions import REGIONS

ORG = {"AUH": "Abu Dhabi Primary Care (simulated)", "YDE": "Yaoundé Health Centre (simulated)"}
_SYNTHETIC_NAMES = {
    "AUH": ["Omar R.", "Layla S.", "Yusuf M.", "Noura A.", "Hamad T.", "Aisha K."],
    "YDE": ["Eric N.", "Solange B.", "Pascal M.", "Rose T.", "Alain D.", "Mireille F."],
}


def initials_of(name: str) -> str:
    parts = [p for p in re.split(r"\W+", name) if p]
    return "".join(p[0].upper() for p in parts[:2])


def default_consents(db: Session, patient: Patient, now: datetime) -> None:
    for purpose, channel, granted in (
        ("care_coordination", None, True), ("messaging_channel", patient.channel, True),
        ("share_with_receiving_provider", None, True), ("lifestyle_programme", None, True), ("research_aggregate", None, False),
    ):
        db.add(Consent(patient_id=patient.id, purpose=purpose, channel=channel, granted=granted,
                       granted_at=now if granted else None))


def primary_clinician_for(db: Session, region: str) -> int | None:
    q = select(User).where(User.role == "clinician", User.region == region, User.active.is_(True),
                           ~User.description.contains("hypertension")).order_by(User.id)
    u = db.scalars(q).first()
    return u.id if u else None


def get_or_create_patient(db: Session, req: S.IntakeRequest, now: datetime) -> Patient:
    existing = db.scalars(select(Patient).where(Patient.ref == req.patient_ref)).first()
    if existing:
        return existing
    region = req.region.value
    spec = req.patient
    name = spec.display_name if spec else _SYNTHETIC_NAMES[region][sum(map(ord, req.patient_ref)) % len(_SYNTHETIC_NAMES[region])]
    lang = (spec.language.value if spec else REGIONS[region]["default_language"])
    patient = Patient(
        ref=req.patient_ref, display_name=name, initials=initials_of(name), age=spec.age if spec else 52,
        sex=spec.sex if spec else "M", nationality_group=spec.nationality_group if spec else ("Other" if region == "AUH" else "Cameroonian"),
        language=lang, region=region, insurance=spec.insurance if spec else "NONE",
        channel=spec.channel.value if spec else ("APP" if region == "AUH" else "SMS"),
        phone=None, organisation=ORG[region], primary_clinician_id=primary_clinician_for(db, region),
    )
    db.add(patient)
    db.flush()
    default_consents(db, patient, now)
    return patient


def open_case(
    db: Session, patient: Patient, readings: list[tuple[int, int, int | None, datetime]], source_system: str, now: datetime,
    scenario: str | None = None,
) -> Case | None:
    """Open a case if any reading is actionable. The worst reading is the index reading."""
    graded = [(engine.classify(s, d), s, d) for s, d, _, _ in readings]
    graded = [g for g in graded if g[0] is not None]
    if not graded:
        return None
    severity, s, d = max(graded, key=lambda g: (g[0] is Severity.SEVERE, g[1], g[2]))
    case = Case(
        patient_id=patient.id, region=patient.region, organisation=patient.organisation, scenario=scenario,
        state=State.RESULT_ISSUED.value, severity=severity.value, index_systolic=s, index_diastolic=d,
        source_system=source_system, opened_at=now, milestones={State.RESULT_ISSUED.value: now.isoformat()},
        step_started_at=now, owner_role=Role.COORDINATOR.value,
    )
    db.add(case)
    db.flush()
    src = ReadingSource.CLINIC.value
    for sys_, dia, pulse, at in readings:
        db.add(Reading(case_id=case.id, systolic=sys_, diastolic=dia, pulse=pulse, taken_at=at, source=src, entered_by_role="system"))
    case.owner_user_id = default_owner(db, case, Role.COORDINATOR)
    log(db, case, now, EventType.CASE_OPENED, to_state=State.RESULT_ISSUED.value,
        payload={"source_system": source_system, "severity": severity.value, "systolic": s, "diastolic": d, "simulated": True})
    if severity is Severity.SEVERE:
        flag_urgent(db, case, now, "SEVERE_READING")
        perform(db, case, None, Role.SYSTEM, Action.NOTIFY,
                {"template_id": "result_severe", "language": patient.language, "channel": patient.channel}, now)
    return case


# ------------------------------------------------------------------ phone thread


_BP = re.compile(r"^(\d{2,3})\s*/\s*(\d{2,3})$")
_CHECKIN = {
    "A": "done", "FAIT": "done", "DONE": "done", "OUI": "done",
    "B": "partly", "PARTIEL": "partly", "PARTLY": "partly",
    "C": "missed", "NON": "missed", "PAS FAIT": "missed", "MISSED": "missed",
}
_STOP = ("STOP", "ARRET", "ARRÊT")
UNPARSED_LIMIT = 2


def parse_bp(text: str) -> tuple[int, int] | None:
    """Strict SYS/DIA pattern, plausible range 60-260 over 30-160. Nothing else counts as a reading."""
    m = _BP.match(text.strip())
    if not m:
        return None
    sys_, dia = int(m.group(1)), int(m.group(2))
    return (sys_, dia) if 60 <= sys_ <= 260 and 30 <= dia <= 160 and sys_ > dia else None


def _unparsed_in_a_row(db: Session, case: Case) -> int:
    rows = db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id, CaseEvent.type == EventType.MESSAGE_RECEIVED.value)
                      .order_by(CaseEvent.id.desc()))
    n = 0
    for e in rows:
        if e.payload.get("parsed", True):
            break
        n += 1
    return n


def handle_reply(db: Session, case: Case, patient: Patient, text: str, now: datetime) -> None:
    """Fixed rules only: 1 understood, 2 call me, STOP, A/B/C weekly check-in, and a strict SYS/DIA reading."""
    add_message(db, case, now, None, text, language=patient.language, channel=patient.channel, direction="IN")
    kw = text.strip().upper()
    user = db.scalars(select(User).where(User.patient_id == patient.id)).first()
    reply: str | None = "reply_received"
    parsed = True
    try:
        bp = parse_bp(text)
        if kw == "2":
            if open_task(db, case.id, "COORDINATOR_CALL") is None:
                add_task(db, case, now, "COORDINATOR_CALL", "call_the_patient", "coordinator", default_owner(db, case, Role.COORDINATOR))
            reply = "call_requested"
        elif kw == "1" and case.state == State.NOTIFIED.value:
            tb = wording_port.teach_back(patient.language, {"reading": f"{case.index_systolic}/{case.index_diastolic}"}, sms=True)
            perform(db, case, user, Role.PATIENT, Action.ACKNOWLEDGE, {"teach_back_answer": str(tb["correct"])}, now)
            reply = "confirmation_hbpm_instructions"
        elif kw in _STOP:
            for ch in ("SMS", "WHATSAPP"):
                perform(db, case, user, Role.PATIENT, Action.UPDATE_CONSENT, {"purpose": "messaging_channel", "granted": False, "channel": ch}, now)
            reply = None
        elif bp and case.state == State.ACKNOWLEDGED.value and case.confirmation_method in (None, "HBPM"):
            if case.confirmation_method is None:
                perform(db, case, user, Role.PATIENT, Action.CHOOSE_CONFIRMATION, {"method": "HBPM"}, now)
            perform(db, case, user, Role.PATIENT, Action.ADD_READING,
                    {"systolic": bp[0], "diastolic": bp[1], "taken_at": now.isoformat(), "source": "HOME_CUFF"}, now)
        elif kw in _CHECKIN and case.state == State.IN_CARE.value and open_week(db, case.id) is not None:
            perform(db, case, user, Role.PATIENT, Action.PLAN_CHECKIN, {"status": _CHECKIN[kw]}, now)
        else:
            parsed = False
    except ApiError:
        parsed = False
    if not parsed:
        reply = "reply_not_understood"
    log(db, case, now, EventType.MESSAGE_RECEIVED, payload={"channel": patient.channel, "parsed": parsed})
    if not parsed and _unparsed_in_a_row(db, case) >= UNPARSED_LIMIT and open_task(db, case.id, "COORDINATOR_CALL") is None:
        add_task(db, case, now, "COORDINATOR_CALL", "call_the_patient", "coordinator", default_owner(db, case, Role.COORDINATOR),
                 payload={"reason": "two replies could not be read"})
    if reply:
        send_template(db, case, now, reply)
