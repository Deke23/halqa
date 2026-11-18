"""Closure gate, SLA and demo clock, queues, referral loop, consent, audit: through HTTP."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import AppendOnlyError, Case, CaseEvent
from tests.conftest import add_hbpm_week, correct_answer, drive_khalid, scenario_id

# ---------------------------------------------------------------- closure gate


@pytest.mark.parametrize("persona", ["patient_auh", "coordinator_auh", "analyst", "nurse_yde"])
def test_non_clinicians_cannot_close(api, app, persona):
    cid = scenario_id(app, "ready_to_close")
    r = api.act(persona, cid, "close", {"evidence_type": "BP_CONTROLLED", "evidence_ref": "reading:1"})
    assert r.status_code == 403, r.text
    assert api.get("clinician_pcp", f"/api/cases/{cid}").json()["state"] == "IN_CARE"


def test_clinician_close_needs_evidence(api, app):
    cid = scenario_id(app, "ready_to_close")
    assert api.act("clinician_pcp", cid, "close", {}).status_code == 422
    assert api.act("clinician_pcp", cid, "close", {"evidence_type": "BP_CONTROLLED"}).status_code == 422
    r = api.act("clinician_pcp", cid, "close", {"evidence_type": "BP_CONTROLLED", "decision_note": "short"})
    assert r.status_code == 422 and r.json()["code"] == "CLOSURE_EVIDENCE_REQUIRED"
    assert api.act("clinician_pcp", cid, "close", {"evidence_type": "NOT_A_TYPE", "evidence_ref": "x"}).status_code == 422
    assert api.get("clinician_pcp", f"/api/cases/{cid}").json()["state"] == "IN_CARE"


def test_clinician_close_with_reference_or_note_succeeds(api, app):
    cid = scenario_id(app, "ready_to_close")
    r = api.act("clinician_pcp", cid, "close", {"evidence_type": "BP_CONTROLLED", "evidence_ref": "reading:last three clinic visits"})
    assert r.status_code == 200 and r.json()["state"] == "CLOSED"
    closure = r.json()["closure"]
    assert closure["evidence_type"] == "BP_CONTROLLED" and closure["closed_by_name"]
    # a second case, closed with a note of at least ten characters
    other = scenario_id(app, "lapsed_plan")
    r = api.act("clinician_pcp", other, "close", {"evidence_type": "OTHER_CLINICAL_DECISION", "decision_note": "Clinician decision after phone review"})
    assert r.status_code == 200 and r.json()["closure"]["decision_note"].startswith("Clinician decision")


def test_close_event_is_audited_and_reopen_returns_to_previous_state(api, app):
    cid = scenario_id(app, "ready_to_close")
    api.act("clinician_pcp", cid, "close", {"evidence_type": "BP_CONTROLLED", "evidence_ref": "reading:9"})
    assert api.act("clinician_pcp", cid, "reopen", {"reason": "no"}).status_code == 422
    r = api.act("clinician_pcp", cid, "reopen", {"reason": "BP rose at the next review"})
    assert r.status_code == 200 and r.json()["state"] == "IN_CARE" and r.json()["closure"] is None
    types = [e["type"] for e in r.json()["timeline"]]
    assert "CASE_CLOSED" in types and "CASE_REOPENED" in types
    assert r.json()["next_step"]["overdue"] is False  # fresh due date


def test_nothing_closes_a_case_on_its_own(api, app):
    """Advance the clock far beyond every service level: no case becomes CLOSED."""
    before = {c["id"] for c in api.queue("clinician_pcp", "all") if c["state"] == "CLOSED"}
    for _ in range(4):
        assert api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 24 * 30}).status_code == 200
    after = {c["id"] for c in api.queue("clinician_pcp", "all") if c["state"] == "CLOSED"}
    assert after == before


# ---------------------------------------------------------------- SLA and demo clock


def test_clock_advance_changes_the_queue(api):
    before = {c["id"] for c in api.queue("coordinator_auh", "overdue")}
    clock0 = api.get("coordinator_auh", "/api/demo/clock").json()
    r = api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 100})
    assert r.status_code == 200 and r.json()["offset_seconds"] == pytest.approx(100 * 3600)
    after = {c["id"] for c in api.queue("coordinator_auh", "overdue")}
    assert before < after, "advancing the clock should make more cases overdue"
    assert api.get("coordinator_auh", "/api/demo/clock").json()["now"] > clock0["now"]


def test_overdue_case_gets_level_1_then_level_2(api, app):
    cid = scenario_id(app, "overdue_ack")
    detail = api.get("coordinator_auh", f"/api/cases/{cid}").json()
    assert detail["next_step"]["overdue"] and detail["next_step"]["escalation_level"] >= 1
    assert detail["flags"]["needs_clinician_decision"]  # contact protocol exhausted, never auto-closed
    assert detail["state"] != "CLOSED"
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 100})
    detail = api.get("coordinator_auh", f"/api/cases/{cid}").json()
    assert detail["next_step"]["escalation_level"] == 2
    assert cid in [c["id"] for c in api.queue("coordinator_auh", "escalated")]
    types = [e["type"] for e in detail["timeline"]]
    assert types.count("ESCALATED") == 2  # level 1 and level 2, written once each
    assert any(t["type"] == "COORDINATOR_CALL" for t in detail["tasks"])


def test_severe_intake_creates_parallel_urgent_review_and_escalates_to_on_call(api):
    body = {"patient_ref": "SIM-SEVERE-1", "source_system": "IFHAS_SCREENING", "region": "AUH",
            "readings": [{"systolic": 185, "diastolic": 115}]}
    r = api.post("coordinator_auh", "/api/intake/result", body)
    assert r.status_code == 200 and r.json()["opened"] and r.json()["severity"] == "SEVERE"
    cid = r.json()["case_id"]
    urgent = api.queue("coordinator_auh", "urgent")
    assert urgent and urgent[0]["id"] == cid and urgent[0]["reason_code"] == "URGENT_SEVERE"
    d = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert d["flags"]["urgent_review_pending"] and "complete_urgent_review" in d["allowed_actions"]
    assert d["emergency_advice"]["number"] == "998"
    assert d["next_step"]["label_key"] != "urgent_clinician_review"  # normal pathway continues
    assert any(t["type"] == "URGENT_REVIEW" and t["status"] == "OPEN" for t in d["tasks"])
    api.post("clinician_pcp", "/api/demo/clock/advance", {"hours": 5})
    d = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert any(e["type"] == "ESCALATED" and e["payload"].get("task") == "urgent_review" for e in d["timeline"])
    # coordinators cannot complete it; the clinician can, and the case stops being urgent
    assert api.act("coordinator_auh", cid, "complete_urgent_review", {"note": "reviewed"}).status_code == 403
    r = api.act("clinician_pcp", cid, "complete_urgent_review", {"note": "Reviewed the reading and spoke to the patient"})
    assert r.status_code == 200 and not r.json()["urgent"]
    assert cid not in [c["id"] for c in api.queue("coordinator_auh", "urgent")]


def test_non_actionable_reading_opens_no_case(api):
    body = {"patient_ref": "SIM-OK", "source_system": "IFHAS_SCREENING", "region": "AUH", "readings": [{"systolic": 139, "diastolic": 89}]}
    r = api.post("coordinator_auh", "/api/intake/result", body)
    assert r.json() == {"opened": False, "case_id": None, "severity": None, "reason": "NOT_ACTIONABLE"}


# ---------------------------------------------------------------- queues


def test_seeded_queues_have_the_named_scenarios(api, app):
    for q, scenario in (("overdue", "overdue_ack"), ("rejected", "rejected_referral"), ("unowned", "unowned")):
        cases = api.queue("coordinator_auh", q)
        assert [c["id"] for c in cases] == [scenario_id(app, scenario)], q
    unowned = api.queue("coordinator_auh", "unowned")[0]
    assert unowned["owner_user_id"] is None and unowned["reason_code"] == "NO_OWNER"
    assert api.queue("coordinator_auh", "rejected")[0]["reason_code"] == "REFERRAL_REJECTED"


def test_severe_intake_lands_first_in_urgent(api):
    api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "DEMO-SEVERE", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                         "readings": [{"systolic": 185, "diastolic": 115}]})
    first = api.queue("coordinator_auh", "urgent")[0]
    assert (first["index_systolic"], first["index_diastolic"]) == (185, 115)
    assert api.queue("coordinator_auh", "all")[0]["id"] == first["id"]  # urgent first overall


def test_region_filter_and_roles(api):
    assert all(c["region"] == "YDE" for c in api.queue("nurse_yde", "all"))
    assert api.get("analyst", "/api/cases").status_code == 403
    assert api.get("patient_auh", "/api/cases").status_code == 403
    assert api.client.get("/api/cases").status_code == 401


# ---------------------------------------------------------------- referral loop and consent


def _pending_referral(app) -> int:
    with app.state.db.session() as s:
        return s.scalars(select(Case.id).where(Case.state == "REFERRED", Case.referral_status == "PENDING", Case.region == "AUH")).first()


def test_referral_reject_reassign_and_rerefer(api, app):
    cid = _pending_referral(app)
    assert api.act("clinician_pcp", cid, "reject_referral", {"reason": "not mine"}).status_code == 403  # not the receiving clinician
    r = api.act("clinician_specialist", cid, "reject_referral", {"reason": "Wrong clinic, needs nephrology review"})
    assert r.status_code == 200
    d = r.json()
    assert d["state"] == "CONFIRMED" and d["referral_status"] == "REJECTED" and d["owner_user_id"] is None
    assert d["referral"]["rejection_reason"].startswith("Wrong clinic")
    assert cid in [c["id"] for c in api.queue("coordinator_auh", "rejected")]
    assert d["next_step"]["label_key"] == "reassign_or_rerefer"

    sara = next(u for u in api.get("coordinator_auh", "/api/users?role=clinician").json() if u["persona"] == "clinician_pcp")
    r = api.act("coordinator_auh", cid, "assign_owner", {"user_id": sara["id"]})
    assert r.status_code == 200 and r.json()["owner_user_id"] == sara["id"]
    assert cid not in [c["id"] for c in api.queue("coordinator_auh", "rejected")]

    r = api.act("clinician_pcp", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Referring to the correct service"})
    assert r.status_code == 200 and r.json()["state"] == "REFERRED" and r.json()["referral_status"] == "PENDING"
    assert len(r.json()["referrals_history"]) == 1


def test_rejected_case_can_also_be_rereferred_directly(api, app):
    cid = _pending_referral(app)
    api.act("clinician_specialist", cid, "reject_referral", {"reason": "Wrong clinic"})
    r = api.act("clinician_pcp", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Second attempt"})
    assert r.status_code == 200 and r.json()["referral_status"] == "PENDING"


def test_withdrawn_sharing_consent_blocks_refer(api):
    cid = drive_khalid(api, "CONFIRMED")
    r = api.act("patient_auh", cid, "update_consent", {"purpose": "share_with_receiving_provider", "granted": False})
    assert r.status_code == 200
    d = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert "refer" not in d["allowed_actions"]
    r = api.act("clinician_pcp", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Raised home average"})
    assert r.status_code == 409 and r.json()["code"] == "CONSENT_WITHDRAWN"
    api.act("patient_auh", cid, "update_consent", {"purpose": "share_with_receiving_provider", "granted": True})
    assert api.act("clinician_pcp", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Raised home average"}).status_code == 200


def test_wrong_state_is_409_and_bad_payload_is_422(api):
    cid = api.case_id("patient_auh")
    r = api.act("clinician_pcp", cid, "refer", {"to_service": "x", "reason": "reason"})
    assert r.status_code == 409 and r.json()["code"] == "WRONG_STATE"
    assert api.act("patient_auh", cid, "acknowledge", {"red_flags": ["not_a_flag"], "teach_back_answer": "1"}).status_code == 422
    assert api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"}).status_code == 409


def test_patient_cannot_read_other_cases_or_staff_routes(api, app):
    other = scenario_id(app, "unowned")
    assert api.get("patient_auh", f"/api/cases/{other}").status_code == 403
    assert api.act("patient_auh", other, "acknowledge", {"teach_back_answer": "2"}).status_code == 403


# ---------------------------------------------------------------- audit


def test_staff_reads_write_case_viewed_events(api, app):
    cid = api.case_id("patient_auh")
    api.get("clinician_pcp", f"/api/cases/{cid}")
    api.get("coordinator_auh", f"/api/cases/{cid}")
    with app.state.db.session() as s:
        n = len(list(s.scalars(select(CaseEvent).where(CaseEvent.case_id == cid, CaseEvent.type == "CASE_VIEWED"))))
    assert n == 2
    api.my_case("patient_auh")
    with app.state.db.session() as s:
        assert len(list(s.scalars(select(CaseEvent).where(CaseEvent.case_id == cid, CaseEvent.type == "CASE_VIEWED")))) == 2


def test_case_events_are_append_only(app):
    with app.state.db.session() as s:
        ev = s.scalars(select(CaseEvent)).first()
        ev.reason = "tampered"
        with pytest.raises(AppendOnlyError):
            s.flush()
        s.rollback()
        ev = s.scalars(select(CaseEvent)).first()
        s.delete(ev)
        with pytest.raises(AppendOnlyError):
            s.flush()
        s.rollback()


def test_patient_view_hides_staff_content(api, app):
    cid = scenario_id(app, "rejected_referral")
    staff = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert staff["view"] == "STAFF" and staff["referral"]["rejection_reason"]
    d = api.my_case("patient_auh")
    assert d["view"] == "PATIENT" and d["tasks"] == [] and d["econsults"] == [] and d["suggested_closure_type"] is None
    assert all(e["payload"] == {} and e["reason"] is None for e in d["timeline"])
    assert d["flags"]["overdue"] is False
    assert "hypertension" not in " ".join(m["text"] for m in d["messages"]).lower()


def test_seeded_ready_to_close_case_is_flagged_ready(api, app):
    from tests.conftest import scenario_id
    cid = scenario_id(app, "ready_to_close")
    d = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert d["flags"]["closure_ready"] and d["next_step"]["label_key"] == "consider_closure"
