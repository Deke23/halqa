"""Test fixtures: a fresh seeded app on a temporary SQLite file for every test."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class Api:
    """Thin helper over TestClient that logs in as personas."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self._tokens: dict[str, dict[str, str]] = {}

    def as_(self, persona: str) -> dict[str, str]:
        if persona not in self._tokens:
            r = self.client.post("/api/auth/guest", json={"persona": persona})
            assert r.status_code == 200, r.text
            self._tokens[persona] = {"Authorization": f"Bearer {r.json()['token']}"}
        return self._tokens[persona]

    def get(self, persona: str, url: str, **kw):
        return self.client.get(url, headers=self.as_(persona), **kw)

    def post(self, persona: str, url: str, json=None):
        return self.client.post(url, headers=self.as_(persona), json=json)

    def act(self, persona: str, case_id: int, action: str, payload: dict | None = None):
        return self.post(persona, f"/api/cases/{case_id}/actions", {"action": action, "payload": payload or {}})

    def my_case(self, persona: str) -> dict:
        r = self.get(persona, "/api/my/case")
        assert r.status_code == 200, r.text
        return r.json()

    def queue(self, persona: str, name: str) -> list[dict]:
        r = self.get(persona, f"/api/cases?queue={name}")
        assert r.status_code == 200, r.text
        return r.json()["cases"]

    def case_id(self, persona: str) -> int:
        return self.my_case(persona)["id"]


@pytest.fixture()
def app(tmp_path):
    application = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}", start_tick=False)
    with TestClient(application) as c:
        application.state.test_client = c
        yield application


@pytest.fixture()
def api(app) -> Api:
    return Api(app.state.test_client)


@pytest.fixture()
def db(app):
    with app.state.db.session() as session:
        yield session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def ago(**kw) -> datetime:
    return utc_now() - timedelta(**kw)


def scenario_id(app, scenario: str) -> int:
    """Seeded named scenarios are found by their scenario label, not by hard-coded ids."""
    from sqlalchemy import select
    from app.db.models import Case
    with app.state.db.session() as session:
        return session.scalars(select(Case.id).where(Case.scenario == scenario)).one()


def correct_answer(case: dict) -> str:
    from app.api import wording_port
    p = case["patient"]
    tb = wording_port.teach_back(p["language"], {"reading": f"{case['index_systolic']}/{case['index_diastolic']}"}, sms=p["channel"] == "SMS")
    return str(tb["correct"])


def add_hbpm_week(api: Api, persona: str, case_id: int, systolic: int = 142, diastolic: int = 90, days: int = 5) -> None:
    """Two readings a day on each of the last `days` days, with the actor given by `persona`."""
    today = utc_now().replace(minute=0, second=0, microsecond=0)
    for d in range(days, 0, -1):
        for hour in (7, 19):
            at = (today - timedelta(days=d)).replace(hour=hour)
            r = api.act(persona, case_id, "add_reading", {"systolic": systolic, "diastolic": diastolic, "taken_at": iso(at), "source": "HOME_CUFF"})
            assert r.status_code == 200, r.text


def drive_khalid(api: Api, upto: str) -> int:
    """Run the Abu Dhabi patient through the loop as the personas, stopping after `upto`."""
    order = ["ACKNOWLEDGED", "CONFIRMED", "REFERRED", "APPOINTMENT_BOOKED", "IN_CARE"]
    cid = api.case_id("patient_auh")
    case = api.my_case("patient_auh")
    r = api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": correct_answer(case), "red_flags": [], "confidence": 4})
    assert r.status_code == 200, r.text
    if upto == "ACKNOWLEDGED":
        return cid
    assert api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"}).status_code == 200
    add_hbpm_week(api, "patient_auh", cid)
    r = api.act("clinician_pcp", cid, "review_confirmation", {"outcome": "CONFIRMED"})
    assert r.status_code == 200, r.text
    if upto == "CONFIRMED":
        return cid
    r = api.act("clinician_pcp", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Raised home average, needs specialist review"})
    assert r.status_code == 200, r.text
    assert api.act("clinician_specialist", cid, "accept_referral").status_code == 200
    if upto == "REFERRED":
        return cid
    slots = api.get("patient_auh", f"/api/cases/{cid}/slots").json()
    r = api.act("patient_auh", cid, "book_appointment", {"slot_id": slots[0]["id"]})
    assert r.status_code == 200, r.text
    if upto == "APPOINTMENT_BOOKED":
        return cid
    r = api.act("clinician_specialist", cid, "record_visit", {"outcome": "TREATMENT_STARTED"})
    assert r.status_code == 200, r.text
    return cid
