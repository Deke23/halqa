"""The three demo flows of SPEC section 11, driven through HTTP only as the personas."""

from __future__ import annotations

from datetime import timedelta

from tests.conftest import add_hbpm_week, correct_answer, iso, scenario_id, utc_now


def test_flow_1_patient_abu_dhabi(api):
    # sees the 152/96 result in Arabic, then English
    case = api.my_case("patient_auh")
    assert (case["index_systolic"], case["index_diastolic"]) == (152, 96) and case["patient"]["language"] == "ar"
    cid = case["id"]
    ar = api.get("patient_auh", "/api/my/messages?language=ar").json()
    en = api.get("patient_auh", "/api/my/messages?language=en").json()
    assert "152/96" in ar[0]["text"] and "152/96" in en[0]["text"] and ar[0]["text"] != en[0]["text"]
    assert case["next_step"]["label_key"] == "patient_acknowledge" and case["owner_name"].startswith("Mariam")

    # teach-back: one wrong answer gets the simpler explanation, then the right one passes
    wrong = "1" if correct_answer(case) != "1" else "3"
    assert api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": wrong, "red_flags": []}).json()["feedback"]["code"] == "TEACH_BACK_RETRY"
    d = api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": correct_answer(case), "red_flags": [], "confidence": 4}).json()
    assert d["state"] == "ACKNOWLEDGED"

    # chooses home monitoring and enters readings with a running average
    d = api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"}).json()
    assert d["next_step"]["label_key"] == "complete_home_readings"
    diary = api.get("patient_auh", "/api/my/diary").json()
    assert diary["hbpm_sample"] and diary["wearable_used_for_bp"] is False
    add_hbpm_week(api, "patient_auh", cid)
    d = api.my_case("patient_auh")
    assert d["confirmation"]["status"] == "CONFIRMED_RAISED" and d["confirmation"]["average_systolic"] >= 135

    # clinician reviews, refers; receiving clinician accepts
    d = api.act("clinician_pcp", cid, "review_confirmation", {"outcome": "CONFIRMED", "note": "Home average raised"}).json()
    assert d["state"] == "CONFIRMED"
    r = api.act("clinician_pcp", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Confirmed raised average"})
    assert r.json()["state"] == "REFERRED" and r.json()["referral"]["to_name"].startswith("Dr Omar")
    assert api.my_case("patient_auh")["referral"]["reason"] == ""  # patient-safe projection
    d = api.act("clinician_specialist", cid, "accept_referral").json()
    assert d["referral_status"] == "ACCEPTED" and d["next_step"]["label_key"] == "book_appointment"

    # books a visit with cover shown first
    slots = api.get("patient_auh", f"/api/cases/{cid}/slots").json()
    assert slots[0]["cover"]["covered"] and slots[0]["cover"]["simulated"]
    d = api.act("patient_auh", cid, "book_appointment", {"slot_id": slots[0]["id"]}).json()
    assert d["state"] == "APPOINTMENT_BOOKED" and d["appointment"]["provider_name"].startswith("Dr Omar")
    d = api.act("clinician_specialist", cid, "record_visit", {"outcome": "TREATMENT_STARTED"}).json()
    assert d["state"] == "IN_CARE"

    # weekly salt action, a missed week, a no-blame check-in and a smaller plan
    plan = api.my_case("patient_auh")["plan"]
    assert plan[0]["action_key"] == "salt" and plan[0]["size"] == "full"
    d = api.act("patient_auh", cid, "plan_checkin", {"status": "missed", "barrier": "WORK_SCHEDULE"}).json()
    assert d["plan"][1]["size"] == "smaller" and d["feedback"]["code"] == "PLAN_SMALLER"
    assert d["next_step"]["overdue"] is False and not any(c["purpose"] == "x" for c in d["consents"])


def test_flow_2_coordinator_and_clinician(api, app):
    # queue shows one overdue, one rejected and one unowned case
    for q in ("overdue", "rejected", "unowned"):
        assert len(api.queue("coordinator_auh", q)) == 1, q

    # simulated severe result 185/115 jumps to same-day review
    r = api.post("coordinator_auh", "/api/intake/result", {
        "patient_ref": "DEMO-SEVERE", "source_system": "IFHAS_SCREENING", "region": "AUH", "readings": [{"systolic": 185, "diastolic": 115}]})
    severe = r.json()["case_id"]
    top = api.queue("coordinator_auh", "urgent")[0]
    assert top["id"] == severe and top["reason_code"] == "URGENT_SEVERE"
    d = api.get("clinician_pcp", f"/api/cases/{severe}").json()
    assert d["flags"]["urgent_review_pending"] and d["messages"][0]["template_id"] == "result_severe"

    # clinician answers an e-consult
    econ = scenario_id(app, "econsult_open")
    ec = api.get("clinician_pcp", f"/api/cases/{econ}").json()["econsults"][0]
    assert api.post("clinician_specialist", f"/api/econsults/{ec['id']}/reply", {"answer": "Please refer to obstetrics first."}).json()["status"] == "ANSWERED"

    # closes a case with a recorded decision; closing without evidence is refused
    ready = scenario_id(app, "ready_to_close")
    refused = api.act("clinician_pcp", ready, "close", {"evidence_type": "BP_CONTROLLED"})
    assert refused.status_code == 422
    assert api.act("coordinator_auh", ready, "close", {"evidence_type": "BP_CONTROLLED", "decision_note": "Coordinator trying to close"}).status_code == 403
    closed = api.act("clinician_pcp", ready, "close", {"evidence_type": "BP_CONTROLLED", "decision_note": "Last three clinic readings at target, reviewed with patient"})
    assert closed.status_code == 200 and closed.json()["state"] == "CLOSED"
    assert closed.json()["closure"]["decision_note"]

    # the dashboard shows the measures
    live = api.get("analyst", "/api/dashboard/live").json()["groups"][0]["measures"]
    names = {m["name"] for m in live}
    assert {"time_to_notification_h", "time_to_acknowledgement_h", "time_to_confirmation_d", "time_to_consultation_d", "time_to_care_d",
            "referral_completion_rate", "appointment_completion_rate", "treatment_initiation_rate", "unresolved_results",
            "teach_back_pass_rate", "patient_confidence_mean", "plan_checkin_rate", "re_engagement_after_lapse_rate"} <= names


def test_flow_3_patient_yaounde_phone_thread(api, app):
    from app.api import auth
    from app.db.models import User
    from sqlalchemy import select

    jp = api.my_case("patient_yde")
    cid = jp["id"]
    thread = api.get("patient_yde", "/api/my/messages").json()
    assert thread[0]["channel"] == "SMS" and thread[0]["language"] == "fr" and "164/102" in thread[0]["text"]
    assert jp["owner_name"].startswith("Clarisse") and jp["owner_role"] == "coordinator"

    # reply 1 = understood, then the red-flag question (1 yes, 2 no); the nurse stays accountable for the patient-facing steps
    thread = api.post("patient_yde", "/api/my/messages/reply", {"text": "1"}).json()
    assert thread[-1]["template_id"] == "red_flag_check" and thread[-1]["language"] == "fr" and len(thread[-1]["text"]) <= 160
    thread = api.post("patient_yde", "/api/my/messages/reply", {"text": "2"}).json()
    assert thread[-1]["template_id"] == "teach_back_question" and "A)" in thread[-1]["text"]
    thread = api.post("patient_yde", "/api/my/messages/reply", {"text": "b."}).json()  # letters, any case, trailing dot allowed
    assert thread[-1]["direction"] == "OUT" and thread[-1]["language"] == "fr" and len(thread[-1]["text"]) <= 160
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == "ACKNOWLEDGED"

    # home readings by SMS, twelve hours apart on the demo clock
    for _ in range(12):
        api.post("patient_yde", "/api/my/messages/reply", {"text": "152/96"})
        api.post("nurse_yde", "/api/demo/clock/advance", {"hours": 12})
    d = api.get("clinician_yde", f"/api/cases/{cid}").json()
    assert d["confirmation"]["status"] == "CONFIRMED_RAISED"
    assert api.act("clinician_yde", cid, "review_confirmation", {"outcome": "CONFIRMED"}).json()["state"] == "CONFIRMED"
    assert api.act("clinician_yde", cid, "refer", {"to_service": "hypertension_clinic", "reason": "Raised home average"}).json()["state"] == "REFERRED"

    # the receiving clinician has a persona too, but one hidden from the picker
    assert api.get("specialist_yde", "/api/me").json()["region"] == "YDE"
    assert api.act("specialist_yde", cid, "accept_referral").json()["referral_status"] == "ACCEPTED"
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["next_step"]["owner_role"] == "coordinator" and d["owner_name"].startswith("Clarisse")

    # the nurse books on the patient's behalf (a coordinator may), cover shown in XAF as simulated
    slots = api.get("nurse_yde", f"/api/cases/{cid}/slots").json()
    assert slots[0]["cover"]["currency"] == "XAF" and slots[0]["cover"]["simulated"]
    assert api.act("nurse_yde", cid, "book_appointment", {"slot_id": slots[0]["id"]}).json()["state"] == "APPOINTMENT_BOOKED"
    assert api.act("specialist_yde", cid, "record_visit", {"outcome": "TREATMENT_STARTED"}).json()["state"] == "IN_CARE"

    # weekly check-in by keyword, the plan shrinks on a missed week
    api.post("patient_yde", "/api/my/messages/reply", {"text": "C"})
    d = api.my_case("patient_yde")
    assert d["plan"][1]["size"] == "smaller"
    assert all(m["language"] == "fr" for m in d["messages"] if m["direction"] == "OUT")
