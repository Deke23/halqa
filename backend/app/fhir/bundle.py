"""Read-only FHIR R4 projection of a case.

The bundle is built from rows and validated by `fhir.resources` (R4B). It is a facade: nothing here
writes to the case. Blood pressure Observations come only from validated cuff or ABPM readings.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from fhir.resources.R4B.bundle import Bundle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Case, CaseEvent, Consent, Patient
from app.api.core import case_data, appointment_of, messages_of, plan_weeks, readings_of, referrals_of, user_name
from app.api.wording_port import plan_text
from app import engine
from app.engine.types import State, STATE_ORDER

LOINC = "http://loinc.org"
BP_PANEL, SYS, DIA = "85354-9", "8480-6", "8462-4"
SIMULATED_TAG = {"system": "https://halqa.invalid/simulated", "code": "simulated", "display": "Synthetic data, not a real person"}


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _ref(kind: str, rid: str, display: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"reference": f"{kind}/{rid}"}
    if display:
        out["display"] = display
    return out


def build_bundle(db: Session, case: Case, now: datetime) -> dict[str, Any]:
    patient = db.get(Patient, case.patient_id)
    pid = f"patient-{patient.id}"
    meta = {"tag": [SIMULATED_TAG]}
    res: list[dict[str, Any]] = [{
        "resourceType": "Patient", "id": pid, "meta": meta,
        "identifier": [{"system": "https://halqa.invalid/patient-ref", "value": patient.ref}],
        "name": [{"text": patient.display_name}], "gender": "female" if patient.sex == "F" else "male",
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": patient.language}]}, "preferred": True}],
    }]

    for r in readings_of(db, case.id):
        res.append({
            "resourceType": "Observation", "id": f"obs-{r.id}", "meta": meta, "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
            "code": {"coding": [{"system": LOINC, "code": BP_PANEL, "display": "Blood pressure panel"}]},
            "subject": _ref("Patient", pid), "effectiveDateTime": _iso(r.taken_at),
            "method": {"text": {"HOME_CUFF": "Validated home cuff", "CLINIC": "Clinic measurement", "ABPM": "Ambulatory monitor"}[r.source]},
            "component": [
                {"code": {"coding": [{"system": LOINC, "code": SYS, "display": "Systolic blood pressure"}]},
                 "valueQuantity": {"value": r.systolic, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}},
                {"code": {"coding": [{"system": LOINC, "code": DIA, "display": "Diastolic blood pressure"}]},
                 "valueQuantity": {"value": r.diastolic, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}},
            ],
        })

    # One Task per pathway step reached, plus the current one. Owner and due date come from the engine.
    current = STATE_ORDER.index(State(case.state))
    ms = case.milestones or {}
    step = engine.next_step(case_data(db, case))
    for i, st in enumerate(STATE_ORDER[:-1]):
        if i > current:
            break
        reached = ms.get(st.value)
        task: dict[str, Any] = {
            "resourceType": "Task", "id": f"task-{case.id}-{st.value.lower().replace(chr(95), chr(45))}", "meta": meta,
            "status": "completed" if i < current or case.state == State.CLOSED.value else "in-progress", "intent": "order",
            "description": st.value, "for": _ref("Patient", pid), "authoredOn": reached,
        }
        if i == current and step is not None and case.state != State.CLOSED.value:
            task["description"] = f"{st.value}: {step.label_key}"
            task["restriction"] = {"period": {"end": _iso(step.due_at)}}
            task["owner"] = {"display": f"{step.owner_role.value}" + (f" ({user_name(db, case.owner_user_id)})" if case.owner_user_id else " (no owner)")}
        res.append(task)

    for ref in referrals_of(db, case.id):
        status = {"PENDING": "active", "ACCEPTED": "completed", "REJECTED": "revoked"}[ref.status]
        sr: dict[str, Any] = {
            "resourceType": "ServiceRequest", "id": f"referral-{ref.id}", "meta": meta, "status": status, "intent": "order",
            "subject": _ref("Patient", pid), "authoredOn": _iso(ref.created_at), "reasonCode": [{"text": ref.reason}],
        }
        if ref.to_user_id:
            sr["performer"] = [{"display": user_name(db, ref.to_user_id)}]
        res.append(sr)

    for m in messages_of(db, case.id):
        res.append({
            "resourceType": "Communication", "id": f"msg-{m.id}", "meta": meta, "status": "completed", "sent": _iso(m.created_at),
            "subject": _ref("Patient", pid), "payload": [{"contentString": m.text}],
            "language": m.language, "medium": [{"text": m.channel}],
        })

    appt = appointment_of(db, case.id)
    if appt:
        res.append({
            "resourceType": "Appointment", "id": f"appt-{appt.id}", "meta": meta,
            "status": {"BOOKED": "booked", "ATTENDED": "fulfilled"}.get(appt.status, "booked"),
            "start": _iso(appt.starts_at), "end": _iso(appt.starts_at + timedelta(minutes=30)),
            "participant": [{"actor": _ref("Patient", pid), "status": "accepted"}, {"actor": {"display": appt.provider_name}, "status": "accepted"}],
        })

    weeks = plan_weeks(db, case.id)
    if weeks:
        res.append({
            "resourceType": "CarePlan", "id": f"careplan-{case.id}", "meta": meta,
            "status": "completed" if case.state == State.CLOSED.value else "active", "intent": "plan", "subject": _ref("Patient", pid),
            "title": "Weekly lifestyle action",
            "activity": [{"detail": {
                "status": {"done": "completed", "partly": "completed", "missed": "not-started", None: "in-progress"}[w.status],
                "kind": "Task", "description": f"Week {w.week_index} ({w.size}): {plan_text(w.action_key, w.size)}",
            }} for w in weeks],
        })

    for c in db.scalars(select(Consent).where(Consent.patient_id == patient.id).order_by(Consent.id)):
        res.append({
            "resourceType": "Consent", "id": f"consent-{c.id}", "meta": meta, "status": "active" if c.granted else "rejected",
            "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy"}]},
            "category": [{"coding": [{"system": LOINC, "code": "59284-0", "display": "Consent document"}], "text": c.purpose}],
            "patient": _ref("Patient", pid), "dateTime": _iso(c.granted_at or c.withdrawn_at) if (c.granted_at or c.withdrawn_at) else None,
        })

    if case.state == State.CLOSED.value and case.closed_at:
        closure = db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id, CaseEvent.type == "CASE_CLOSED")
                             .order_by(CaseEvent.id.desc())).first()
        res.append({
            "resourceType": "Provenance", "id": f"prov-{case.id}", "meta": meta,
            "target": [_ref("Patient", pid)], "recorded": _iso(case.closed_at),
            "reason": [{"text": f"{case.closure_evidence_type}: {case.closure_evidence_ref or case.closure_decision_note}"}],
            "agent": [{"who": {"display": user_name(db, case.closed_by_user_id) or "clinician"},
                       "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type", "code": "author"}]}}],
            "activity": {"text": "Case closed by clinician" + (f" (event {closure.id})" if closure else "")},
        })

    entries = []
    for r in res:
        r = {k: v for k, v in r.items() if v is not None}
        entries.append({"fullUrl": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, r['resourceType'] + '/' + r['id'])}", "resource": r})
    bundle = Bundle.model_validate({"resourceType": "Bundle", "id": f"case-{case.id}", "type": "collection",
                                    "timestamp": _iso(now), "entry": entries})
    return json.loads(bundle.model_dump_json(exclude_none=True))
