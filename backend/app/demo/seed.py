"""Deterministic demo data: seven personas and 24 cases covering every named scenario.

All people, readings and providers are fictional and generated here. Timestamps are
relative to the seed time, so overdue cases are overdue right after a reset.
Real organisation names (IFHAS, Thiqa) appear only as labels of simulated sources.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.api.core import STAFF, add_task, log, refresh_case, send_message, start_plan, sync_owner
from app.api.intake import default_consents, initials_of
from app.db.models import (
    Appointment, Case, Consent, DemoClock, EConsult, Patient, PlanWeek, Reading, Referral, Slot, User,
)
from app.engine import plan as plan_rules
from app.engine.types import CheckinStatus, EventType, State, STATE_ORDER

AUH_ORG = "Abu Dhabi Primary Care (simulated)"
AUH_SPEC_ORG = "Hypertension Clinic Abu Dhabi (simulated)"
YDE_ORG = "Yaoundé Health Centre (simulated)"
YDE_SPEC_ORG = "Yaoundé Regional Hypertension Clinic (simulated)"

# Service levels in hours, used only to place seeded steps safely inside or outside their window.
SL = {"RESULT_ISSUED": 24, "NOTIFIED": 72, "ACKNOWLEDGED": 336, "CONFIRMED": 72, "REFERRED": 48, "REFERRED_ACCEPTED": 120, "IN_CARE": 672}


# Seeded people (by the number in their reference) who have not opted in to research_aggregate: the dashboard leaves them out.
NOT_IN_RESEARCH = (13, 17)
# Abu Dhabi app patients (by number in their reference) who have agreed to the app only, so the suppression path shows in the demo.
NO_SMS_CONSENT = (0, 10, 14)


def h(now: datetime, hours: float) -> datetime:
    return now - timedelta(hours=hours)


def seed(db: Session, now: datetime) -> None:
    rng = random.Random(20260614)
    u = _users(db)
    _slots(db, now, u)
    db.flush()

    # ---- the two patient personas
    khalid = _patient(db, now, "KHALID-AUH", "Khalid A.", 34, "M", "Emirati", "ar", "AUH", "THIQA", "APP", u["sara"].id,
                      "+971-000-0001", persona="patient_auh", desc="Khalid, 34, Emirati, Thiqa member, office job with irregular hours. Flagged at a simulated IFHAS screening, 152/96. Arabic or English.")
    jp = _patient(db, now, "JEANPAUL-YDE", "Jean-Paul E.", 47, "M", "Cameroonian", "fr", "YDE", "NONE", "SMS", u["brice"].id,
                  "+237-000-0001", persona="patient_yde", desc="Jean-Paul, 47, taxi driver in Yaoundé. Clinic reading 164/102. French, SMS and WhatsApp thread only.")
    _case(db, now, rng, khalid, 152, 96, "IFHAS_SCREENING", "NOTIFIED", step_age=3, scenario="patient_auh", ack_pass=None)
    _case(db, now, rng, jp, 164, 102, "CLINIC_READING", "NOTIFIED", step_age=2, scenario="patient_yde", ack_pass=None)

    # ---- named scenarios
    c = _case(db, now, rng, _extra(db, now, rng, "AUH", 0), 158, 98, "IFHAS_SCREENING", "NOTIFIED", step_age=5 * 24, scenario="overdue_ack")
    c = _case(db, now, rng, _extra(db, now, rng, "AUH", 1), 166, 100, "IFHAS_SCREENING", "CONFIRMED", step_age=20, scenario="rejected_referral",
              referral="REJECTED", rejection="Wrong clinic, needs nephrology review")
    c = _case(db, now, rng, _extra(db, now, rng, "AUH", 2, unowned=True), 148, 94, "IFHAS_SCREENING", "CONFIRMED", step_age=30, scenario="unowned")
    _case(db, now, rng, _extra(db, now, rng, "AUH", 3), 150, 92, "IFHAS_SCREENING", "IN_CARE", step_age=500, scenario="ready_to_close",
          at_target=True, plan=[CheckinStatus.DONE, CheckinStatus.DONE, CheckinStatus.DONE])
    econ = _case(db, now, rng, _extra(db, now, rng, "AUH", 4), 160, 101, "IFHAS_SCREENING", "CONFIRMED", step_age=20, scenario="econsult_open")
    db.add(EConsult(case_id=econ.id, from_user_id=u["sara"].id, to_user_id=u["omar"].id,
                    question="Reading average is raised but the patient is 27 weeks pregnant per the referral note. Should referral go to obstetrics first?",
                    created_at=h(now, 6)))
    log(db, econ, h(now, 6), EventType.ECONSULT_ASKED, u["sara"], payload={"to_user_id": u["omar"].id})
    _case(db, now, rng, _extra(db, now, rng, "AUH", 5), 154, 96, "IFHAS_SCREENING", "IN_CARE", step_age=300, scenario="lapsed_plan",
          plan=[CheckinStatus.PARTLY, CheckinStatus.MISSED, CheckinStatus.MISSED], plan_open_age_days=2)

    # ---- fill the rest of the pathway, about 24 cases in total
    fill = [
        ("AUH", "RESULT_ISSUED", 3), ("YDE", "RESULT_ISSUED", 10),
        ("YDE", "NOTIFIED", 12), ("AUH", "NOTIFIED", 20),
        ("AUH", "ACKNOWLEDGED", 150), ("YDE", "ACKNOWLEDGED", 90), ("AUH", "ACKNOWLEDGED_INSUFFICIENT", 18),
        ("YDE", "CONFIRMED", 10),
        ("AUH", "REFERRED", 30), ("YDE", "REFERRED", 10),
        ("AUH", "APPOINTMENT_BOOKED", 0), ("YDE", "APPOINTMENT_BOOKED", 0),
        ("AUH", "IN_CARE", 350), ("YDE", "IN_CARE", 200),
        ("AUH", "CLOSED:BP_CONTROLLED", 0), ("YDE", "CLOSED:PATIENT_DECLINED", 0),
    ]
    for i, (region, state, age) in enumerate(fill):
        _case(db, now, rng, _extra(db, now, rng, region, 10 + i), rng.randint(142, 176), rng.randint(90, 106), "IFHAS_SCREENING" if region == "AUH" else "CLINIC_READING",
              state, step_age=age, plan=[CheckinStatus.DONE, CheckinStatus.DONE] if (state == "IN_CARE" and region == "AUH") else
              ([CheckinStatus.PARTLY] if state == "IN_CARE" else None))

    db.flush()
    for case in db.query(Case).order_by(Case.id):
        refresh_case(db, case, now)  # protocol steps for the overdue case, nothing else fires
    db.get(DemoClock, 1) or db.add(DemoClock(id=1, offset_seconds=0.0))
    db.commit()


# ------------------------------------------------------------------ users and slots


def _users(db: Session) -> dict[str, User]:
    spec = [
        ("coordinator_auh", "mariam", "Mariam (care coordinator)", "coordinator", "AUH", AUH_ORG, "en", "Care coordinator, Abu Dhabi primary care. Sees the queue."),
        ("clinician_pcp", "sara", "Dr Sara (family medicine)", "clinician", "AUH", AUH_ORG, "en", "Family medicine. Reviews confirmation, refers, answers and asks e-consults, closes."),
        ("clinician_specialist", "omar", "Dr Omar (hypertension clinic)", "clinician", "AUH", AUH_SPEC_ORG, "en", "Hypertension clinic. Accepts or rejects referrals, treats."),
        ("nurse_yde", "clarisse", "Clarisse (nurse coordinator)", "coordinator", "YDE", YDE_ORG, "fr", "Nurse coordinator, Yaoundé health centre. Coordinator role in the Cameroon region."),
        ("analyst", "analyst", "Programme analyst", "analyst", "AUH", "Programme office (simulated)", "en", "Dashboard only. Sees aggregates, never individuals."),
        ("clinician_yde", "brice", "Dr Brice (general practice, Yaoundé)", "clinician", "YDE", YDE_ORG, "fr", "General practice, Yaoundé health centre."),
        ("specialist_yde", "estelle", "Dr Estelle (hypertension clinic, Yaoundé)", "clinician", "YDE", YDE_SPEC_ORG, "fr", "Hypertension clinic, Yaoundé."),
        (None, "nadia", "Dr Nadia (has left the organisation)", "clinician", "AUH", AUH_ORG, "en", "Former family medicine clinician. Inactive."),
    ]
    out: dict[str, User] = {}
    for persona, key, name, role, region, org, lang, desc in spec:
        user = User(persona_key=persona, name=name, role=role, region=region, organisation=org, language=lang, description=desc,
                    active=key != "nadia")
        db.add(user)
        out[key] = user
    db.flush()
    return out


def _slots(db: Session, now: datetime, u: dict[str, User]) -> None:
    base = now.replace(minute=0, second=0, microsecond=0)
    for region, who, where in (
        ("AUH", u["omar"], "Hypertension Clinic Abu Dhabi (simulated)"),
        ("YDE", u["estelle"], "Yaoundé Regional Hypertension Clinic (simulated)"),
    ):
        for day in range(2, 12):
            for hour in (6, 9):
                db.add(Slot(region=region, starts_at=(base + timedelta(days=day)).replace(hour=hour), provider_name=who.name,
                            location=where, clinician_id=who.id))


# ------------------------------------------------------------------ patients


_FIRST = {
    "AUH": ["Rashed", "Maryam", "Hessa", "Zayed", "Latifa", "Nasser", "Sultan", "Amna", "Faisal", "Dina", "Imran", "Priya", "Arjun", "Salma", "Tariq", "Huda"],
    "YDE": ["Eric", "Solange", "Pascal", "Rose", "Alain", "Mireille", "Joseph", "Berthe", "Landry", "Estelle", "Fabrice", "Nadine", "Cyrille", "Odette", "Hermann", "Judith"],
}
_GROUPS = ["Emirati", "Expatriate Arab", "South Asian", "Other"]


def _patient(db: Session, now: datetime, ref: str, name: str, age: int, sex: str, group: str, lang: str, region: str,
             insurance: str, channel: str, primary: int | None, phone: str, persona: str | None = None, desc: str = "",
             research: bool = True) -> Patient:
    org = AUH_ORG if region == "AUH" else YDE_ORG
    p = Patient(ref=ref, display_name=name, initials=initials_of(name), age=age, sex=sex, nationality_group=group, language=lang,
                region=region, insurance=insurance, channel=channel, phone=phone, organisation=org, primary_clinician_id=primary)
    db.add(p)
    db.flush()
    default_consents(db, p, h(now, 2000), research=research)  # research use is opt-in; a few seeded people have not opted in
    # Explicit app and SMS consent, so the reminder protocol can use its second channel. A few people have not agreed to SMS.
    no_sms = ref.startswith("SYN-AUH-") and int(ref[-3:]) in NO_SMS_CONSENT
    for ch in ("APP", "SMS"):
        if ch != channel and not (ch == "SMS" and no_sms):
            db.add(Consent(patient_id=p.id, purpose="messaging_channel", channel=ch, granted=True, granted_at=h(now, 2000)))
    if persona:
        db.add(User(persona_key=persona, name=name, role="patient", region=region, organisation=org, language=lang,
                    patient_id=p.id, description=desc))
    return p


def _extra(db: Session, now: datetime, rng: random.Random, region: str, n: int, unowned: bool = False) -> Patient:
    users = {x.persona_key or x.name: x for x in db.query(User)}
    sara = users["clinician_pcp"].id
    brice = users["clinician_yde"].id
    nadia = next(x.id for x in db.query(User) if x.name.startswith("Dr Nadia"))
    first = _FIRST[region][n % 16]
    name = f"{first} {chr(65 + (n * 7) % 26)}."
    if region == "AUH":
        group = _GROUPS[n % 4]
        lang = "ar" if group in ("Emirati", "Expatriate Arab") else "en"
        insurance = "THIQA" if group == "Emirati" else rng.choice(["BASIC", "BASIC", "NONE"])
        channel = "APP"
    else:
        group, lang, insurance, channel = "Cameroonian", "fr", "NONE", rng.choice(["SMS", "WHATSAPP"])
    primary = nadia if unowned else (sara if region == "AUH" else brice)
    return _patient(db, now, f"SYN-{region}-{n:03d}", name, rng.randint(29, 71), rng.choice(["F", "M"]), group, lang, region,
                    insurance, channel, primary, f"+000-555-{n:04d}", research=n not in NOT_IN_RESEARCH)


# ------------------------------------------------------------------ cases


def _case(
    db: Session, now: datetime, rng: random.Random, patient: Patient, sys_: int, dia: int, source: str, state_spec: str, *,
    step_age: float, scenario: str | None = None, referral: str | None = None, rejection: str | None = None,
    at_target: bool = False, plan: list[CheckinStatus] | None = None, plan_open_age_days: float = 2, ack_pass: bool | None = True,
) -> Case:
    closed_with = None
    if state_spec.startswith("CLOSED:"):
        closed_with = state_spec.split(":", 1)[1]
        target = State.IN_CARE if closed_with == "BP_CONTROLLED" else State.NOTIFIED
        step_age = 400 if target is State.IN_CARE else 150
        at_target = closed_with == "BP_CONTROLLED"
    elif state_spec == "ACKNOWLEDGED_INSUFFICIENT":
        target = State.ACKNOWLEDGED
    else:
        target = State(state_spec)
    coord = next(x for x in db.query(User) if x.role == "coordinator" and x.region == patient.region)
    pcp = db.get(User, patient.primary_clinician_id)
    spec_user = next(x for x in db.query(User) if x.role == "clinician" and x.region == patient.region and "hypertension" in x.description.lower())

    # milestone times, built backwards from the age of the current step
    idx = STATE_ORDER.index(target)
    gaps = {"NOTIFIED": rng.uniform(1, 14), "ACKNOWLEDGED": rng.uniform(4, 40), "CONFIRMED": rng.uniform(150, 240), "REFERRED": rng.uniform(4, 36),
            "APPOINTMENT_BOOKED": rng.uniform(30, 90), "IN_CARE": rng.uniform(100, 200)}
    times: dict[State, datetime] = {}
    if target is State.APPOINTMENT_BOOKED:
        appt_at = now + timedelta(days=rng.choice([1, 3, 5]))
        times[target] = h(now, rng.uniform(20, 60))
    elif target is State.REFERRED and referral is None and patient.region and step_age < 20:
        times[target] = h(now, step_age)
    elif referral == "REJECTED":
        times[target] = h(now, step_age + 30)  # confirmed earlier; the step restarted when the referral came back
    else:
        times[target] = h(now, step_age)
    accepted_at: datetime | None = None
    if target is State.REFERRED and (step_age < 20):
        # accepted referral: booking sub-step is the current step and is patient-acting, keep it under 24 hours
        accepted_at = h(now, step_age)
        times[target] = accepted_at - timedelta(hours=rng.uniform(4, 30))
    for i in range(idx, 0, -1):
        st = STATE_ORDER[i]
        prev = STATE_ORDER[i - 1]
        times[prev] = times[st] - timedelta(hours=gaps.get(st.value, 6))
    opened = times[State.RESULT_ISSUED]
    if closed_with:
        closed_at = h(now, rng.uniform(30, 120))
        times[State.CLOSED] = closed_at

    case = Case(
        patient_id=patient.id, region=patient.region, organisation=patient.organisation, scenario=scenario, state=target.value,
        severity="RAISED", index_systolic=sys_, index_diastolic=dia, source_system=source, opened_at=opened,
        milestones={s.value: t.isoformat() for s, t in times.items() if STATE_ORDER.index(s) <= idx},
        step_started_at=times[target], owner_role="coordinator",
    )
    if target is State.APPOINTMENT_BOOKED:
        case.step_started_at = appt_at
    if accepted_at:
        case.step_started_at = accepted_at
    if referral == "REJECTED":
        case.step_started_at = h(now, step_age)
    db.add(case)
    db.flush()

    db.add(Reading(case_id=case.id, systolic=sys_, diastolic=dia, taken_at=opened, source="CLINIC", entered_by_role="system"))
    log(db, case, opened, EventType.CASE_OPENED, to_state=State.RESULT_ISSUED.value,
        payload={"source_system": source, "severity": "RAISED", "systolic": sys_, "diastolic": dia, "simulated": True})

    def ev(t: State, type_: EventType, actor: User | None, frm: State, **kw: Any) -> None:
        log(db, case, times[t], type_, actor, from_state=frm.value, to_state=t.value, **kw)

    if idx >= 1:
        t_n = times[State.NOTIFIED]
        # Written through the one send function, in the patient's language, with the due date of the acknowledge step as it was then.
        due = {"due_at": (t_n + timedelta(hours=72)).isoformat()}
        # The in-app thread also holds the teach-back question; an SMS thread gets it after the red-flag question (reply grammar).
        first_messages = ("result_raised", "teach_back_question") if target is State.NOTIFIED and patient.channel == "APP" else ("result_raised",)
        for i, tid in enumerate(first_messages):
            send_message(db, case, t_n, tid, kind=STAFF, sender=coord, extra=due,
                         transition=(State.RESULT_ISSUED.value, State.NOTIFIED.value) if i == 0 else None)
    if idx >= 2:
        case.teach_back_first_pass = rng.random() < 0.75 if ack_pass else ack_pass
        case.patient_confidence = rng.randint(3, 5)
        ev(State.ACKNOWLEDGED, EventType.TEACH_BACK_PASSED, None, State.NOTIFIED, payload={"confidence": case.patient_confidence})
        case.confirmation_method = "HBPM"
        ack_t = times[State.ACKNOWLEDGED]
        days = 2 if state_spec == "ACKNOWLEDGED_INSUFFICIENT" else 5
        for d in range(days):
            if idx == 2:  # recent readings: yesterday and earlier
                day = (now - timedelta(days=days - d)).replace(minute=0, second=0, microsecond=0)
            else:  # readings in the days after acknowledgement
                day = (ack_t + timedelta(days=1 + d)).replace(minute=0, second=0, microsecond=0)
            for slot_h in (6, 18):
                db.add(Reading(case_id=case.id, systolic=138 + rng.randint(0, 8), diastolic=86 + rng.randint(0, 6),
                               taken_at=day.replace(hour=slot_h), source="HOME_CUFF", entered_by_role="patient"))
    if idx >= 3:
        ev(State.CONFIRMED, EventType.CONFIRMATION_REVIEWED, pcp, State.ACKNOWLEDGED, payload={"outcome": "CONFIRMED"})
    if idx >= 4 or (target is State.CONFIRMED and referral):
        refs_status = "ACCEPTED" if idx > 4 or accepted_at else "PENDING"
        if target is State.CONFIRMED:
            refs_status = "REJECTED"
        ref_t = times.get(State.REFERRED, h(now, step_age + 10))
        r = Referral(case_id=case.id, from_user_id=pcp.id if pcp else None, to_user_id=spec_user.id, reason="Raised average on home monitoring, needs specialist review",
                     status=refs_status, created_at=ref_t, decided_at=None if refs_status == "PENDING" else (h(now, step_age) if refs_status == "REJECTED" else (accepted_at or ref_t + timedelta(hours=8))))
        if refs_status == "REJECTED":
            r.rejection_reason = rejection or "Wrong clinic"
        db.add(r)
        case.referral_status = refs_status
        log(db, case, ref_t, EventType.REFERRAL_SENT, pcp, from_state=State.CONFIRMED.value, to_state=State.REFERRED.value,
            payload={"to_user_id": spec_user.id}, reason=r.reason)
        if refs_status == "ACCEPTED":
            log(db, case, r.decided_at, EventType.REFERRAL_ACCEPTED, spec_user)
        if refs_status == "REJECTED":
            log(db, case, r.decided_at, EventType.REFERRAL_REJECTED, spec_user, from_state=State.REFERRED.value,
                to_state=State.CONFIRMED.value, reason=r.rejection_reason)
    if idx >= 5:
        slot_t = appt_at if target is State.APPOINTMENT_BOOKED else times[State.IN_CARE] - timedelta(hours=2)
        db.add(Appointment(case_id=case.id, starts_at=slot_t, provider_name=spec_user.name, location=spec_user.organisation,
                           status="BOOKED" if target is State.APPOINTMENT_BOOKED else "ATTENDED", created_at=times[State.APPOINTMENT_BOOKED]))
        ev(State.APPOINTMENT_BOOKED, EventType.APPOINTMENT_BOOKED, coord, State.REFERRED)
    if idx >= 6:
        case.visit_outcome = "TREATMENT_STARTED" if rng.random() < 0.85 else "SURVEILLANCE"
        ev(State.IN_CARE, EventType.VISIT_RECORDED, spec_user, State.APPOINTMENT_BOOKED, payload={"outcome": case.visit_outcome})
        if plan is not None:
            _plan(db, case, times[State.IN_CARE], plan, now, plan_open_age_days)
        if at_target:
            for k in range(3):
                db.add(Reading(case_id=case.id, systolic=122 + k, diastolic=76 + k, taken_at=h(now, 24 * (21 - 7 * k)), source="CLINIC", entered_by_role="clinician"))
    db.flush()

    if closed_with:
        closed_at = times[State.CLOSED]
        case.state_before_close = target.value
        case.state = State.CLOSED.value
        case.milestones = {**case.milestones, State.CLOSED.value: closed_at.isoformat()}
        case.closed_at, case.closed_by_user_id = closed_at, pcp.id
        case.closure_evidence_type = closed_with
        note = "Patient declined further follow-up after discussion with the clinician" if closed_with == "PATIENT_DECLINED" else None
        case.closure_evidence_ref = "reading:last-three-clinic-visits" if closed_with == "BP_CONTROLLED" else None
        case.closure_decision_note = note
        log(db, case, closed_at, EventType.CASE_CLOSED, pcp, from_state=target.value, to_state=State.CLOSED.value,
            payload={"evidence_type": closed_with, "evidence_ref": case.closure_evidence_ref}, reason=note)
        case.owner_user_id = None
        return case

    sync_owner(db, case)
    if referral == "REJECTED":
        case.owner_user_id, case.owner_role = None, "coordinator"
    return case


def _plan(db: Session, case: Case, start: datetime, statuses: list[CheckinStatus], now: datetime, open_age_days: float) -> None:
    """Build plan weeks by replaying the real plan rules over the given check-ins."""
    action, size = plan_rules.first_week()
    open_start = now - timedelta(days=open_age_days)
    week_start = open_start - timedelta(days=7 * len(statuses))
    history: list[plan_rules.PlanWeekData] = []
    index = 1
    offered = False
    for status in statuses:
        db.add(PlanWeek(case_id=case.id, week_index=index, action_key=action.value, size=size.value, status=status.value,
                        offered_larger=offered, starts_at=week_start, checked_in_at=week_start + timedelta(days=5)))
        history.append(plan_rules.PlanWeekData(action, size, status, offered))
        d = plan_rules.decide_next(history)
        action, size, offered = d.action_key, d.size, d.offer_larger
        index += 1
        week_start += timedelta(days=7)
    db.add(PlanWeek(case_id=case.id, week_index=index, action_key=action.value, size=size.value, offered_larger=offered,
                    starts_at=open_start))
