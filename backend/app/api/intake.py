"""Opening cases from a simulated screening or clinic feed, and the phone-thread reply parser.

Safety property: replies are parsed by fixed keywords and one numeric pattern only. No model
reads a patient's text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Case, CaseEvent, Consent, Patient, Reading, User
from app.engine.types import Action, EventType, ReadingSource, Role, Severity, State

from . import schemas as S
from .actions_impl import Ctx, perform, record_red_flags
from .core import (
    FINAL, REPLY, SAFETY_REPLY, ApiError, add_message, add_task, contact_other_route_task, default_owner, explicit_consent, flag_urgent, log,
    open_task, open_week, plan_active, send_message,
)
from . import wording_port
from .regions import REGIONS, is_stop_keyword

ORG = {"AUH": "Abu Dhabi Primary Care (simulated)", "YDE": "Yaoundé Health Centre (simulated)"}
_SYNTHETIC_NAMES = {
    "AUH": ["Omar R.", "Layla S.", "Yusuf M.", "Noura A.", "Hamad T.", "Aisha K."],
    "YDE": ["Eric N.", "Solange B.", "Pascal M.", "Rose T.", "Alain D.", "Mireille F."],
}


def initials_of(name: str) -> str:
    parts = [p for p in re.split(r"\W+", name) if p]
    return "".join(p[0].upper() for p in parts[:2])


def default_consents(db: Session, patient: Patient, now: datetime, research: bool = False) -> None:
    """The consent records a new patient starts with. Research use is opt-in: it is off unless `research` is True."""
    for purpose, channel, granted in (
        ("care_coordination", None, True), ("messaging_channel", patient.channel, True),
        ("share_with_receiving_provider", None, True), ("lifestyle_programme", None, True), ("research_aggregate", None, research),
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


# ------------------------------------------------------------------ SMS reply grammar
#
# One table, state-driven (SPEC section 6). Yes/no questions take digits, multiple-choice questions take letters, so a
# number can never be read as a teach-back answer. `0` (call me) and STOP work in every state.

CALL_ME = "0"
_TRAILING = re.compile(r"[.)\]]+$")
LETTERS = ("A", "B", "C")


@dataclass
class Turn:
    db: Session
    case: Case
    patient: Patient
    user: User | None
    now: datetime
    text: str
    token: str  # upper case, trailing dot or bracket removed
    replies: list[tuple[str, str, dict]] = field(default_factory=list)  # template id, kind, neutral extras

    def say(self, template_id: str, kind: str = REPLY, **extra) -> None:
        self.replies.append((template_id, kind, extra))

    def do(self, action: Action, payload: dict) -> None:
        perform(self.db, self.case, self.user, Role.PATIENT, action, payload, self.now)


def _read_result(t: Turn) -> None:
    t.case.sms_prompt = "RED_FLAG"
    t.say("red_flag_check")


def _red_flag_answer(yes: bool):
    def handler(t: Turn) -> None:
        if yes:
            ctx = Ctx(t.db, t.case, t.user, Role.PATIENT, t.now)
            record_red_flags(ctx, ["unspecified"])  # the same urgent flag and audit event as the app path
            t.say("urgent_red_flags_sms" if t.patient.channel == "SMS" else "urgent_red_flags", SAFETY_REPLY)
        t.case.sms_prompt = "TEACH_BACK"
        t.say("teach_back_question")
    return handler


def _teach_back_answer(t: Turn) -> None:
    # No confidence rating is asked on SMS: it stays empty rather than getting an invented value.
    t.do(Action.ACKNOWLEDGE, {"teach_back_answer": str(LETTERS.index(t.token) + 1), "red_flags": []})
    if t.case.state == State.ACKNOWLEDGED.value:
        t.case.sms_prompt = None
        t.say("confirmation_hbpm_instructions")
    else:  # wrong: the simpler explanation was sent by the action; ask again (a second wrong answer made the call task)
        t.say("teach_back_question")


def _checkin(t: Turn) -> None:
    t.do(Action.PLAN_CHECKIN, {"status": _CHECKIN[t.token]})
    t.say("reply_received")


# state -> accepted token -> handler
REPLY_GRAMMAR: dict[str, dict[str, Callable[[Turn], None]]] = {
    "RESULT": {"1": _read_result},
    "RED_FLAG": {"1": _red_flag_answer(True), "OUI": _red_flag_answer(True), "2": _red_flag_answer(False), "NON": _red_flag_answer(False)},
    "TEACH_BACK": {letter: _teach_back_answer for letter in LETTERS},
    "HOME": {},  # a strict SYS/DIA reading, handled in handle_reply
    "CHECKIN": {k: _checkin for k in _CHECKIN},
}


def reply_state(db: Session, case: Case) -> str:
    """Where the SMS conversation is, from the case: this picks the row of REPLY_GRAMMAR."""
    if case.state == State.NOTIFIED.value:
        return case.sms_prompt if case.sms_prompt in ("RED_FLAG", "TEACH_BACK") else "RESULT"
    if case.state == State.ACKNOWLEDGED.value and case.confirmation_method in (None, "HBPM"):
        return "HOME"
    if case.state == State.IN_CARE.value and plan_active(db, case) and open_week(db, case.id) is not None:
        return "CHECKIN"
    return "NONE"


# What the latest outbound message offers, for quick-reply buttons: state -> [(reply, meaning_key)]
VALID_REPLIES: dict[str, list[tuple[str, str]]] = {
    "RESULT": [("1", "reply.read")],
    "RED_FLAG": [("1", "reply.yes"), ("2", "reply.no")],
    "TEACH_BACK": [("A", "reply.option_a"), ("B", "reply.option_b"), ("C", "reply.option_c")],
    "HOME": [("SYS/DIA", "reply.reading")],
    "CHECKIN": [("A", "reply.done"), ("B", "reply.partly"), ("C", "reply.missed")],
    "NONE": [],
}


def valid_replies(db: Session, case: Case) -> list[tuple[str, str]]:
    return VALID_REPLIES[reply_state(db, case)] + [(CALL_ME, "reply.call_me")]


def handle_reply(db: Session, case: Case, patient: Patient, text: str, now: datetime) -> None:
    """Fixed rules only. No model reads the text. See REPLY_GRAMMAR, and the severe-reading and STOP rules below.

    A severe reading gets the urgent template with the region's emergency instruction, not the generic reply.
    """
    chan = patient.channel
    add_message(db, case, now, None, text, language=patient.language, channel=chan, direction="IN")
    user = db.scalars(select(User).where(User.patient_id == patient.id)).first()
    token = _TRAILING.sub("", text.strip().upper())
    state = reply_state(db, case)
    t = Turn(db, case, patient, user, now, text, token)
    parsed = True
    try:
        bp = parse_bp(text)
        if is_stop_keyword(text):
            was_active = explicit_consent(db, patient.id, "messaging_channel", chan)
            t.do(Action.UPDATE_CONSENT, {"purpose": "messaging_channel", "granted": False, "channel": chan})
            contact_other_route_task(db, case, now)
            if was_active:  # one final fixed confirmation, not one per repeated STOP
                t.say("stop_confirmed", FINAL)
            else:
                t.say("")
        elif token == CALL_ME:
            if open_task(db, case.id, "COORDINATOR_CALL") is None:
                add_task(db, case, now, "COORDINATOR_CALL", "call_the_patient", "coordinator", default_owner(db, case, Role.COORDINATOR))
            t.say("call_requested")
        elif token in REPLY_GRAMMAR.get(state, {}):
            REPLY_GRAMMAR[state][token](t)
        elif bp and state == "HOME":
            if case.confirmation_method is None:
                t.do(Action.CHOOSE_CONFIRMATION, {"method": "HBPM"})
            t.do(Action.ADD_READING, {"systolic": bp[0], "diastolic": bp[1], "taken_at": now.isoformat(), "source": "HOME_CUFF"})
            if engine.classify(bp[0], bp[1]) is Severity.SEVERE:
                t.say("result_severe", SAFETY_REPLY, systolic=bp[0], diastolic=bp[1], reading=f"{bp[0]}/{bp[1]}")
            else:
                t.say("reply_received")
        else:
            parsed = False
    except ApiError:
        parsed = False
    if not parsed:
        t.replies = [("reply_not_understood", REPLY, {})]
        if state == "RED_FLAG":  # say the open question again so the valid replies are in front of the patient
            t.say("red_flag_check")
        elif state == "TEACH_BACK":
            t.say("teach_back_question")
    elif not t.replies:
        t.say("reply_received")
    log(db, case, now, EventType.MESSAGE_RECEIVED, payload={"channel": chan, "parsed": parsed})
    if not parsed and _unparsed_in_a_row(db, case) >= UNPARSED_LIMIT and open_task(db, case.id, "COORDINATOR_CALL") is None:
        add_task(db, case, now, "COORDINATOR_CALL", "call_the_patient", "coordinator", default_owner(db, case, Role.COORDINATOR),
                 payload={"reason": "two replies could not be read"})
    for template_id, kind, extra in t.replies:
        if template_id:
            send_message(db, case, now, template_id, kind=kind, extra=extra)
