"""Aggregate dashboard. Safety property: no individual data, and any cell with fewer than 5 people is suppressed.

`live` is computed from cases in the database. `simulation` serves the precomputed file from workstream D.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine
from app.db.models import Appointment, Case, Consent, Patient, PlanWeek, Referral, User
from app.demo import clock
from app.engine.demographics import AGE_BANDS, age_band  # noqa: F401  (one definition, shared with the simulation)
from app.engine.types import State

from . import schemas as S
from .constants import DATA_DIR
from .core import case_data
from .deps import anyone_but_patient, get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
MIN_CELL = 5


def _ts(case: Case, state: State) -> datetime | None:
    raw = (case.milestones or {}).get(state.value)
    return datetime.fromisoformat(raw) if raw else None


def _hours(a: datetime | None, b: datetime | None) -> float | None:
    return None if a is None or b is None else (b - a).total_seconds() / 3600


def _timing(name: str, unit: str, values: list[float], per_day: bool) -> S.Measure:
    n = len(values)
    if n < MIN_CELL:
        return S.Measure(name=name, unit=unit, n=n, suppressed=True)
    vals = [v / 24 for v in values] if per_day else values
    p90 = statistics.quantiles(vals, n=10, method="inclusive")[-1]
    return S.Measure(name=name, unit=unit, n=n, suppressed=False, median=round(statistics.median(vals), 1), p90=round(p90, 1))


def _rate(name: str, hits: int, n: int) -> S.Measure:
    if n < MIN_CELL:
        return S.Measure(name=name, unit="share", n=n, suppressed=True)
    return S.Measure(name=name, unit="share", n=n, suppressed=False, value=round(hits / n, 3), count=hits)


def delay_reason(case: Case, cd, ev) -> str | None:
    """Why an open case counts as unresolved, from engine flags only."""
    if cd.state is State.CLOSED:
        return None
    from .projection import flags_of
    f = flags_of(cd, ev, case)
    if f.care_coordination_withdrawn:
        return "care_coordination_withdrawn"
    if f.rejected:
        return "referral_rejected"
    if f.unowned:
        return "no_owner"
    if f.needs_clinician_decision:
        return "patient_not_reached"
    if f.overdue:
        return {"NOTIFIED": "awaiting_patient_acknowledgement", "ACKNOWLEDGED": "awaiting_confirmation",
                "REFERRED": "awaiting_referral_or_booking", "APPOINTMENT_BOOKED": "awaiting_visit_outcome"}.get(case.state, "step_overdue")
    return None


def measures_for(db: Session, cases: list[Case], now: datetime) -> list[S.Measure]:
    ids = [c.id for c in cases]
    refs: dict[int, list[Referral]] = defaultdict(list)
    for r in db.scalars(select(Referral).where(Referral.case_id.in_(ids)).order_by(Referral.id)):
        refs[r.case_id].append(r)
    appts = {a.case_id: a for a in db.scalars(select(Appointment).where(Appointment.case_id.in_(ids)).order_by(Appointment.id))}
    weeks: dict[int, list[PlanWeek]] = defaultdict(list)
    for w in db.scalars(select(PlanWeek).where(PlanWeek.case_id.in_(ids)).order_by(PlanWeek.week_index)):
        weeks[w.case_id].append(w)

    t_notif, t_ack, t_conf, t_cons, t_care = [], [], [], [], []
    for c in cases:
        opened, notified, acked = c.opened_at, _ts(c, State.NOTIFIED), _ts(c, State.ACKNOWLEDGED)
        confirmed, in_care = _ts(c, State.CONFIRMED), _ts(c, State.IN_CARE)
        for lst, v in ((t_notif, _hours(opened, notified)), (t_ack, _hours(notified, acked)), (t_conf, _hours(opened, confirmed)),
                       (t_cons, _hours(opened, in_care))):
            if v is not None:
                lst.append(v)
        if c.visit_outcome == "TREATMENT_STARTED" and in_care:
            t_care.append(_hours(opened, in_care))

    with_ref = [c for c in cases if refs.get(c.id)]
    ref_ok = sum(1 for c in with_ref if refs[c.id][-1].status == "ACCEPTED")
    with_appt = [c for c in cases if c.id in appts]
    appt_ok = sum(1 for c in with_appt if appts[c.id].status == "ATTENDED")
    visited = [c for c in cases if c.visit_outcome]
    treated = sum(1 for c in visited if c.visit_outcome == "TREATMENT_STARTED")

    unresolved: list[str] = []
    for c in cases:
        cd = case_data(db, c)
        reason = delay_reason(c, cd, engine.evaluate(cd, now))
        if reason:
            unresolved.append(reason)
    counts = Counter(unresolved)
    total_unresolved = len(unresolved)
    if total_unresolved < MIN_CELL:
        unres = S.Measure(name="unresolved_results", unit="cases", n=total_unresolved, suppressed=True)
    else:
        unres = S.Measure(
            name="unresolved_results", unit="cases", n=total_unresolved, suppressed=False, count=total_unresolved,
            value=round(total_unresolved / len(cases), 3) if cases else None,
            delay_reasons=[S.DelayReason(reason=r, n=n, suppressed=n < MIN_CELL) for r, n in sorted(counts.items())],
        )

    tb = [c for c in cases if c.teach_back_first_pass is not None]
    conf = [c.patient_confidence for c in cases if c.patient_confidence]
    plan_cases = [c for c in cases if any(w.status for w in weeks.get(c.id, []))]
    closed_weeks = [w for c in plan_cases for w in weeks[c.id] if w.status]
    checked = sum(1 for w in closed_weeks if w.status in ("done", "partly"))
    lapsed = [c for c in cases if any(w.status == "missed" for w in weeks.get(c.id, []))]
    back = 0
    for c in lapsed:
        ws = weeks[c.id]
        first_miss = next(i for i, w in enumerate(ws) if w.status == "missed")
        back += any(w.status in ("done", "partly") for w in ws[first_miss + 1:])

    conf_m = (S.Measure(name="patient_confidence_mean", unit="score 1 to 5", n=len(conf), suppressed=True) if len(conf) < MIN_CELL else
              S.Measure(name="patient_confidence_mean", unit="score 1 to 5", n=len(conf), suppressed=False, value=round(statistics.mean(conf), 2)))
    plan_m = (S.Measure(name="plan_checkin_rate", unit="share", n=len(plan_cases), suppressed=True) if len(plan_cases) < MIN_CELL else
              S.Measure(name="plan_checkin_rate", unit="share", n=len(plan_cases), suppressed=False,
                        value=round(checked / len(closed_weeks), 3), count=checked))
    return [
        _timing("time_to_notification_h", "hours", t_notif, False),
        _timing("time_to_acknowledgement_h", "hours", t_ack, False),
        _timing("time_to_confirmation_d", "days", t_conf, True),
        _timing("time_to_consultation_d", "days", t_cons, True),
        _timing("time_to_care_d", "days", t_care, True),
        _rate("referral_completion_rate", ref_ok, len(with_ref)),
        _rate("appointment_completion_rate", appt_ok, len(with_appt)),
        _rate("treatment_initiation_rate", treated, len(visited)),
        unres,
        _rate("teach_back_pass_rate", sum(1 for c in tb if c.teach_back_first_pass), len(tb)),
        conf_m, plan_m,
        _rate("re_engagement_after_lapse_rate", back, len(lapsed)),
    ]


_SPLITS: dict[S.Split, Callable[[Patient], str]] = {
    S.Split.LANGUAGE: lambda p: p.language,
    S.Split.NATIONALITY_GROUP: lambda p: p.nationality_group,
    S.Split.SEX: lambda p: p.sex,
    S.Split.AGE_BAND: lambda p: age_band(p.age),
}


@router.get("/live", response_model=S.DashboardLive)
def live(split: S.Split = S.Split.NONE, region: S.Region | None = None,
         user: User = Depends(anyone_but_patient), db: Session = Depends(get_db)):
    now = clock.now(db)
    # Only people who opted in to research_aggregate are counted in any aggregate (a missing record is not consent).
    opted_in = select(Consent.patient_id).where(Consent.purpose == "research_aggregate", Consent.granted.is_(True))
    q = select(Case, Patient).join(Patient, Patient.id == Case.patient_id).where(Patient.id.in_(opted_in))
    if region:
        q = q.where(Case.region == region.value)
    pairs = list(db.execute(q.order_by(Case.id)).all())
    groups: dict[str, list[Case]] = defaultdict(list)
    for case, patient in pairs:
        groups["all" if split is S.Split.NONE else _SPLITS[split](patient)].append(case)
    if not groups:
        groups["all"] = []
    out = [S.DashboardGroup(key=k, label=k if k != "all" else "All people", measures=measures_for(db, cs, now))
           for k, cs in sorted(groups.items())]
    return S.DashboardLive(split=split, region=region, generated_at=now, min_cell_size=MIN_CELL, groups=out)


@router.get("/simulation", response_model=S.SimulationResponse)
def simulation(split: S.Split = S.Split.NONE, user: User = Depends(anyone_but_patient)):
    path = DATA_DIR / "simulation_results.json"
    if not path.exists():
        return JSONResponse({"available": False})
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = {"available": True, **data}
        splits = data.get("splits")
        if isinstance(splits, dict) and split.value in splits:
            data["selected_split"] = splits[split.value]
        return JSONResponse(data)
    return JSONResponse({"available": True, "results": data})
