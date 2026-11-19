"""Demo clock and reset, FHIR facade, and the patient diary series."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Case, User
from app.demo import clock
from app.demo.seed import seed
from app.engine.types import EventType
from app.fhir.bundle import build_bundle

from . import schemas as S
from .constants import DATA_DIR
from .core import ApiError, log, tick_all
from .demo_mode import require_demo
from .deps import anyone_but_patient, clinician_only, current_user, get_db, load_case, patient_only

router = APIRouter(prefix="/api")


def _clock_out(db: Session) -> S.ClockOut:
    return S.ClockOut(now=clock.now(db), real_now=clock.real_now(), offset_seconds=clock.offset_seconds(db))


@router.get("/demo/clock", response_model=S.ClockOut, tags=["demo"])
def get_clock(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _clock_out(db)


@router.post("/demo/clock/advance", response_model=S.ClockOut, tags=["demo"],
             summary="Advance the demo clock and re-evaluate every open case")
def advance_clock(req: S.AdvanceRequest, _demo: None = Depends(require_demo), user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """Demo control. Any signed-in guest may skip ahead (the patient demo shortcut); DEMO_MODE off answers 403."""
    now = clock.advance(db, req.hours)
    tick_all(db, now)
    return _clock_out(db)


@router.post("/demo/reset", response_model=S.ResetResponse, tags=["demo"], summary="Restore the seeded demo data exactly")
def reset(request: Request, _demo: None = Depends(require_demo), user: User = Depends(anyone_but_patient)):
    """Demo control. Needs a signed-in staff or analyst user; DEMO_MODE off answers 403. Drops and recreates the schema."""
    database = request.app.state.db
    database.reset_schema()  # DDL: the only way audit events are removed
    with database.session() as db:
        seed(db, clock.real_now())
        return S.ResetResponse(reset=True, cases=db.scalar(select(func.count(Case.id))), clock=_clock_out(db))


@router.get("/cases/{case_id}/fhir", tags=["cases"], summary="FHIR R4 Bundle for the case (read-only, clinician only)")
def case_fhir(case_id: int, user: User = Depends(clinician_only), db: Session = Depends(get_db)):
    case = load_case(db, user, case_id)
    now = clock.now(db)
    log(db, case, now, EventType.CASE_VIEWED, user, payload={"view": "fhir"})
    db.commit()
    return build_bundle(db, case, now)


@router.get("/my/diary", response_model=S.DiaryOut, tags=["patient"])
def my_diary(user: User = Depends(patient_only)):
    path = DATA_DIR / "demo_series.json"
    if user.persona_key is None or not path.exists():
        raise ApiError(404, "NO_DIARY", "No sample series for this user.")
    data = json.loads(path.read_text(encoding="utf-8"))
    p = data["personas"].get(user.persona_key)
    if p is None:
        raise ApiError(404, "NO_DIARY", "No sample series for this user.")
    return S.DiaryOut(
        wearable_days=[S.DiaryDay(**d) for d in p["wearable_diary"]["days"]], wearable_note=p["wearable_diary"]["note"],
        hbpm_sample=[S.SampleReading(day=r["day"], time=r["time"], systolic=r["systolic"], diastolic=r["diastolic"], pulse=r.get("pulse"))
                     for r in p["hbpm_week"]["readings"]],
        abpm_sample=[S.SampleReading(day=1, time=r["time"], systolic=r["systolic"], diastolic=r["diastolic"], pulse=r.get("pulse"))
                     for r in p["abpm_day"]["readings"]],
        disclaimer=data["disclaimer"],
    )
