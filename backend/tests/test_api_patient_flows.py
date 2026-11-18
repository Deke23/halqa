"""Teach-back, red flags, lifestyle plan, phone thread, dashboard suppression, FHIR, wording isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api import wording_port
from app.db.models import Case
from app.fhir.bundle import build_bundle
from tests.conftest import correct_answer, drive_khalid, scenario_id, utc_now

# ---------------------------------------------------------------- teach-back and red flags


def test_wrong_teach_back_does_not_advance_and_second_wrong_creates_call_task(api):
    cid = api.case_id("patient_auh")
    case = api.my_case("patient_auh")
    assert case["teach_back"]["options"], "the result screen carries the teach-back question"
    wrong = "1" if correct_answer(case) != "1" else "3"
    r = api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": wrong, "red_flags": []})
    assert r.status_code == 200
    d = r.json()
    assert d["state"] == "NOTIFIED"
    assert d["feedback"]["code"] == "TEACH_BACK_RETRY" and d["feedback"]["message"]
    assert not any(t["type"] == "TEACH_BACK_CALL" for t in api.get("coordinator_auh", f"/api/cases/{cid}").json()["tasks"])

    d = api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": wrong, "red_flags": []}).json()
    assert d["state"] == "NOTIFIED"
    tasks = api.get("coordinator_auh", f"/api/cases/{cid}").json()["tasks"]
    assert [t["type"] for t in tasks].count("TEACH_BACK_CALL") == 1

    d = api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": correct_answer(case), "red_flags": [], "confidence": 5}).json()
    assert d["state"] == "ACKNOWLEDGED"
    assert d["next_step"]["label_key"] == "choose_confirmation_method"


def test_red_flag_escalates_to_urgent_with_region_advice(api):
    cid = api.case_id("patient_auh")
    case = api.my_case("patient_auh")
    r = api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": correct_answer(case), "red_flags": ["chest_pain"]})
    d = r.json()
    assert d["urgent"] and d["feedback"]["code"] == "RED_FLAG_EMERGENCY"
    assert d["emergency_advice"]["number"] == "998"
    assert api.queue("coordinator_auh", "urgent")[0]["id"] == cid
    # Cameroon gives advice without a number
    jp = api.my_case("patient_yde")
    d = api.act("patient_yde", jp["id"], "acknowledge", {"teach_back_answer": "x", "red_flags": ["confusion"]}).json()
    assert d["emergency_advice"]["number"] is None and "urgences" in d["emergency_advice"]["text"]


def test_wearable_is_not_a_blood_pressure_source(api):
    cid = drive_khalid(api, "ACKNOWLEDGED")
    r = api.act("patient_auh", cid, "add_reading", {"systolic": 150, "diastolic": 90, "taken_at": utc_now().isoformat(), "source": "WEARABLE"})
    assert r.status_code == 422
    r = api.act("patient_auh", cid, "add_reading", {"systolic": 150, "diastolic": 90, "taken_at": utc_now().isoformat(), "source": "CLINIC"})
    assert r.status_code == 403  # a patient cannot enter a clinic reading
    diary = api.get("patient_auh", "/api/my/diary").json()
    assert diary["wearable_used_for_bp"] is False and diary["wearable_days"]


def test_confirmation_steps_do_not_change_state_and_insufficient_cannot_be_reviewed(api):
    cid = drive_khalid(api, "ACKNOWLEDGED")
    d = api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"}).json()
    assert d["state"] == "ACKNOWLEDGED" and d["next_step"]["label_key"] == "complete_home_readings"
    r = api.act("clinician_pcp", cid, "review_confirmation", {"outcome": "CONFIRMED"})
    assert r.status_code == 409 and r.json()["code"] == "INSUFFICIENT_READINGS"
    from tests.conftest import add_hbpm_week
    add_hbpm_week(api, "patient_auh", cid)
    d = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert d["state"] == "ACKNOWLEDGED" and d["next_step"]["label_key"] == "clinician_review_confirmation"
    assert d["confirmation"]["status"] == "CONFIRMED_RAISED"


def test_not_confirmed_keeps_acknowledged_and_never_auto_closes(api):
    cid = drive_khalid(api, "ACKNOWLEDGED")
    api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"})
    from tests.conftest import add_hbpm_week
    add_hbpm_week(api, "patient_auh", cid, systolic=122, diastolic=76)
    assert api.get("clinician_pcp", f"/api/cases/{cid}").json()["confirmation"]["status"] == "NOT_CONFIRMED"
    d = api.act("clinician_pcp", cid, "review_confirmation", {"outcome": "NOT_CONFIRMED", "note": "Home average normal"}).json()
    assert d["state"] == "ACKNOWLEDGED" and d["suggested_closure_type"] == "NOT_CONFIRMED"
    assert d["next_step"]["label_key"] == "clinician_closure_decision" and d["next_step"]["service_level_h"] == 72
    assert d["owner_name"].startswith("Dr Sara")
    d = api.act("clinician_pcp", cid, "close", {"evidence_type": "NOT_CONFIRMED", "decision_note": "Home average below threshold"}).json()
    assert d["state"] == "CLOSED"


# ---------------------------------------------------------------- lifestyle plan


def test_plan_rules_through_the_api(api):
    cid = drive_khalid(api, "IN_CARE")
    d = api.my_case("patient_auh")
    assert d["state"] == "IN_CARE" and d["plan"][0]["size"] == "full" and d["plan"][0]["action_key"] == "salt"

    d = api.act("patient_auh", cid, "plan_checkin", {"status": "missed", "barrier": "TIME"}).json()
    assert d["plan"][0]["status"] == "missed"
    assert d["plan"][1]["size"] == "smaller" and d["plan"][1]["action_key"] == "salt"
    assert d["feedback"]["code"] == "PLAN_SMALLER" and d["feedback"]["message"]
    assert not any(t["type"] == "PLAN_CALL_OFFER" for t in api.get("coordinator_auh", f"/api/cases/{cid}").json()["tasks"])

    # two done in a row: a larger size is offered, never forced
    api.act("patient_auh", cid, "plan_checkin", {"status": "done"})
    d = api.act("patient_auh", cid, "plan_checkin", {"status": "done"}).json()
    assert d["plan"][-1]["offered_larger"] and d["plan"][-1]["size"] == "smaller"
    d = api.act("patient_auh", cid, "plan_checkin", {"status": "done", "accept_larger": True}).json()
    assert d["plan"][-1]["size"] == "full"
    # history is never reset
    assert [w["status"] for w in d["plan"] if w["status"]] == ["missed", "done", "done", "done"]


def test_three_missed_checkins_create_a_human_task(api):
    cid = drive_khalid(api, "IN_CARE")
    for _ in range(3):
        api.act("patient_auh", cid, "plan_checkin", {"status": "missed"})
    d = api.get("coordinator_auh", f"/api/cases/{cid}").json()
    tasks = [t for t in d["tasks"] if t["type"] == "PLAN_CALL_OFFER"]
    assert len(tasks) == 1 and tasks[0]["owner_role"] == "coordinator" and tasks[0]["status"] == "OPEN"
    assert d["plan"][-1]["size"] == "smallest"
    api.act("patient_auh", cid, "plan_checkin", {"status": "missed"})
    assert len([t for t in api.get("coordinator_auh", f"/api/cases/{cid}").json()["tasks"] if t["type"] == "PLAN_CALL_OFFER"]) == 1


def test_lapsed_week_is_recorded_as_missed_without_blame(api, app):
    cid = scenario_id(app, "lapsed_plan")
    before = api.get("clinician_specialist", f"/api/cases/{cid}").json()
    assert [w["status"] for w in before["plan"] if w["status"]] == ["partly", "missed", "missed"]
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 24 * 9})
    after = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert [w["status"] for w in after["plan"] if w["status"]][-1] == "missed"
    assert any(t["type"] == "PLAN_CALL_OFFER" for t in after["tasks"])  # third missed week


def test_no_penalty_language_in_plan_texts(api):
    cid = drive_khalid(api, "IN_CARE")
    d = api.act("patient_auh", cid, "plan_checkin", {"status": "missed"}).json()
    text = (d["feedback"]["message"] + " ".join(w["default_text"] for w in d["plan"])).lower()
    for word in ("streak", "failed", "penalty", "lost", "reset"):
        assert word not in text


# ---------------------------------------------------------------- phone thread (Yaounde)


def test_phone_thread_keywords_and_strict_bp_pattern(api):
    jp = api.my_case("patient_yde")["id"]
    thread = api.get("patient_yde", "/api/my/messages").json()
    assert thread and thread[0]["channel"] == "SMS" and thread[0]["language"] == "fr"

    api.post("patient_yde", "/api/my/messages/reply", {"text": "1"})
    d = api.get("nurse_yde", f"/api/cases/{jp}").json()
    assert d["state"] == "ACKNOWLEDGED" and d["owner_name"].startswith("Dr Brice")

    for bad in ("300/95", "150-95", "bonjour"):
        thread = api.post("patient_yde", "/api/my/messages/reply", {"text": bad}).json()
        assert "150/95" in thread[-1]["text"] or thread[-1]["text"]
    d = api.get("nurse_yde", f"/api/cases/{jp}").json()
    assert d["confirmation"] is None or d["confirmation"]["readings_used"] == 0
    assert [t["type"] for t in d["tasks"]].count("COORDINATOR_CALL") == 1  # created after two unreadable replies in a row

    api.post("patient_yde", "/api/my/messages/reply", {"text": "150/95"})
    d = api.get("nurse_yde", f"/api/cases/{jp}").json()
    assert d["confirmation"]["method"] == "HBPM" and d["readings"][-1]["systolic"] == 150 and d["readings"][-1]["source"] == "HOME_CUFF"


def test_phone_call_me_creates_a_coordinator_task(api):
    jp = api.my_case("patient_yde")["id"]
    api.post("patient_yde", "/api/my/messages/reply", {"text": "2"})
    tasks = api.get("nurse_yde", f"/api/cases/{jp}").json()["tasks"]
    assert any(t["type"] == "COORDINATOR_CALL" and t["owner_role"] == "coordinator" for t in tasks)


def test_phone_stop_withdraws_channel_consent(api):
    jp = api.my_case("patient_yde")["id"]
    api.post("patient_yde", "/api/my/messages/reply", {"text": "STOP"})
    d = api.my_case("patient_yde")
    assert any(c["purpose"] == "messaging_channel" and c["channel"] == "SMS" and not c["granted"] for c in d["consents"])
    r = api.act("nurse_yde", jp, "notify", {"template_id": "reminder_ack", "language": "fr", "channel": "SMS"})
    assert r.status_code in (409,)  # wrong state or withdrawn channel, both refuse


# ---------------------------------------------------------------- messages: draft, approve, send


def test_ai_reworded_draft_needs_approval(api, app):
    cid = scenario_id(app, "unowned")
    d = api.post("coordinator_auh", f"/api/cases/{cid}/messages/draft", {"template_id": "reminder_ack", "language": "en"}).json()
    assert d["source"] == "TEMPLATE" and d["text"]
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft": d})
    assert r.status_code == 200
    ai = {**d, "source": "AI_REWORDED"}
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft": ai})
    assert r.status_code == 409 and r.json()["code"] == "APPROVAL_REQUIRED"
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft": ai, "approve": True})
    assert r.status_code == 200 and r.json()["message"]["approved_by_name"].startswith("Mariam")


def test_engine_and_actions_work_with_wording_disabled(api, monkeypatch):
    monkeypatch.setattr(wording_port, "_wording", lambda: None)
    cid = drive_khalid(api, "ACKNOWLEDGED")
    assert api.my_case("patient_auh")["state"] == "ACKNOWLEDGED"
    assert api.get("coordinator_auh", "/api/config").json()["templates"]


# ---------------------------------------------------------------- e-consult


def test_econsult_ask_and_reply(api, app):
    cid = scenario_id(app, "econsult_open")
    d = api.get("clinician_pcp", f"/api/cases/{cid}").json()
    assert d["econsults"][0]["status"] == "OPEN"
    assert api.get("coordinator_auh", f"/api/cases/{cid}").json()["econsults"] == []  # operational view only
    ec = d["econsults"][0]["id"]
    assert api.post("clinician_pcp", f"/api/econsults/{ec}/reply", {"answer": "I answer my own question"}).status_code == 403
    r = api.post("clinician_specialist", f"/api/econsults/{ec}/reply", {"answer": "Refer to obstetrics first, then to us."})
    assert r.status_code == 200 and r.json()["status"] == "ANSWERED"
    assert api.post("clinician_specialist", f"/api/econsults/{ec}/reply", {"answer": "Again please"}).status_code == 409
    omar = next(u for u in api.get("coordinator_auh", "/api/users").json() if u["persona"] == "clinician_specialist")
    r = api.post("clinician_pcp", f"/api/cases/{cid}/econsults", {"to_user_id": omar["id"], "question": "Is a repeat ABPM useful here?"})
    assert r.status_code == 200 and r.json()["status"] == "OPEN"
    types = [e["type"] for e in api.get("clinician_pcp", f"/api/cases/{cid}").json()["timeline"]]
    assert "ECONSULT_ASKED" in types and "ECONSULT_ANSWERED" in types


# ---------------------------------------------------------------- slots and cover


def test_slots_show_simulated_cover_first(api):
    cid = drive_khalid(api, "REFERRED")
    slots = api.get("patient_auh", f"/api/cases/{cid}/slots").json()
    assert slots and slots[0]["cover"]["simulated"] is True and slots[0]["cover"]["covered"] is True and "Thiqa" in slots[0]["cover"]["label"]
    yde = api.my_case("patient_yde")["id"]
    ys = api.get("patient_yde", f"/api/cases/{yde}/slots").json()
    assert ys[0]["cover"]["currency"] == "XAF" and ys[0]["cover"]["estimated_price"] and ys[0]["cover"]["simulated"] is True
    r = api.act("patient_auh", cid, "book_appointment", {"slot_id": slots[0]["id"]})
    assert r.status_code == 200
    again = api.act("coordinator_auh", cid, "book_appointment", {"slot_id": slots[0]["id"]})
    assert again.status_code == 409


# ---------------------------------------------------------------- dashboard


def test_dashboard_suppresses_small_cells(api):
    for split in ("none", "language", "nationality_group", "sex", "age_band"):
        r = api.get("analyst", f"/api/dashboard/live?split={split}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["min_cell_size"] == 5 and body["groups"]
        for g in body["groups"]:
            names = {m["name"] for m in g["measures"]}
            assert {"time_to_notification_h", "unresolved_results", "teach_back_pass_rate", "re_engagement_after_lapse_rate",
                    "time_to_care_d", "plan_checkin_rate", "patient_confidence_mean"} <= names
            for m in g["measures"]:
                assert m["suppressed"] == (m["n"] < 5), (split, g["key"], m)
                if m["suppressed"]:
                    assert m["value"] is None and m["median"] is None and m["p90"] is None and m["delay_reasons"] is None
    none = api.get("analyst", "/api/dashboard/live").json()["groups"][0]["measures"]
    notif = next(m for m in none if m["name"] == "time_to_notification_h")
    assert not notif["suppressed"] and notif["median"] is not None
    unresolved = next(m for m in none if m["name"] == "unresolved_results")
    assert unresolved["suppressed"]  # only three unresolved cases are seeded
    split = api.get("analyst", "/api/dashboard/live?split=nationality_group").json()["groups"]
    assert any(m["suppressed"] for g in split for m in g["measures"]), "small groups must be suppressed"


def test_dashboard_is_aggregate_only_and_staff_or_analyst(api):
    assert api.get("patient_auh", "/api/dashboard/live").status_code == 403
    text = api.get("analyst", "/api/dashboard/live?split=sex").text
    for forbidden in ("Khalid", "patient_ref", "display_name", "initials"):
        assert forbidden not in text
    assert api.get("analyst", "/api/cases").status_code == 403


def test_dashboard_simulation_serves_file_or_unavailable(api):
    body = api.get("analyst", "/api/dashboard/simulation").json()
    assert "available" in body


def test_live_dashboard_region_filter(api):
    r = api.get("analyst", "/api/dashboard/live?region=YDE")
    assert r.status_code == 200 and r.json()["region"] == "YDE"


# ---------------------------------------------------------------- FHIR


def test_every_seeded_case_produces_a_valid_bundle(app):
    with app.state.db.session() as s:
        cases = list(s.scalars(select(Case)))
        assert len(cases) >= 24
        for case in cases:
            bundle = build_bundle(s, case, utc_now())  # validated by fhir.resources while building
            kinds = [e["resource"]["resourceType"] for e in bundle["entry"]]
            assert kinds.count("Patient") == 1 and "Observation" in kinds and "Task" in kinds, case.id
            if case.state == "CLOSED":
                assert "Provenance" in kinds
            for e in bundle["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Observation":
                    codes = {c["code"] for c in r["code"]["coding"]}
                    comps = {c["code"]["coding"][0]["code"] for c in r["component"]}
                    assert codes == {"85354-9"} and comps == {"8480-6", "8462-4"}


def test_fhir_route_returns_bundle_with_all_resource_kinds(api):
    cid = drive_khalid(api, "IN_CARE")
    api.act("patient_auh", cid, "plan_checkin", {"status": "partly"})
    r = api.get("clinician_pcp", f"/api/cases/{cid}/fhir")
    assert r.status_code == 200 and r.json()["resourceType"] == "Bundle"
    kinds = {e["resource"]["resourceType"] for e in r.json()["entry"]}
    assert {"Patient", "Observation", "Task", "ServiceRequest", "Communication", "Appointment", "CarePlan", "Consent"} <= kinds
    task = next(e["resource"] for e in r.json()["entry"] if e["resource"]["resourceType"] == "Task" and "restriction" in e["resource"])
    assert task["restriction"]["period"]["end"] and task["owner"]["display"]
    assert api.get("patient_auh", f"/api/cases/{cid}/fhir").status_code == 403


# ---------------------------------------------------------------- reset and config


def test_reset_restores_the_seed(api):
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 200})
    cid = api.case_id("patient_auh")
    api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": correct_answer(api.my_case("patient_auh")), "red_flags": []})
    r = api.client.post("/api/demo/reset")
    assert r.status_code == 200 and r.json()["cases"] >= 24 and r.json()["clock"]["offset_seconds"] == 0
    api._tokens.clear()
    assert api.my_case("patient_auh")["state"] == "NOTIFIED"
    assert len(api.queue("coordinator_auh", "overdue")) == 1


def test_seed_is_deterministic_in_shape(app, api):
    with app.state.db.session() as s:
        states = sorted(c.state for c in s.scalars(select(Case)))
        scenarios = {c.scenario for c in s.scalars(select(Case)) if c.scenario}
    assert {"overdue_ack", "rejected_referral", "unowned", "ready_to_close", "econsult_open", "lapsed_plan"} <= scenarios
    assert set(states) == {"RESULT_ISSUED", "NOTIFIED", "ACKNOWLEDGED", "CONFIRMED", "REFERRED", "APPOINTMENT_BOOKED", "IN_CARE", "CLOSED"}
    assert 22 <= len(states) <= 26


def test_config_is_transparent(api):
    c = api.client.get("/api/config").json()
    assert all(e["status"] == "placeholder_pending_clinician_signoff" and e["basis"] for e in c["entries"])
    assert "OTHER_CLINICAL_DECISION" in c["closure_evidence_types"] and c["app_name"]
    assert any("AI only drafts" in r for r in c["rules"])
    assert api.client.get("/api/personas").json()[0]["persona"]


def test_result_message_keeps_index_reading_after_home_readings(api):
    """Re-rendering the thread in a language must not swap the result reading for the latest home reading."""
    cid = drive_khalid(api, "ACKNOWLEDGED")
    assert api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"}).status_code == 200
    r = api.act("patient_auh", cid, "add_reading", {"systolic": 131, "diastolic": 83, "taken_at": utc_now().isoformat(), "source": "HOME_CUFF"})
    assert r.status_code == 200
    for lang in ("en", "ar", "fr"):
        thread = api.get("patient_auh", f"/api/my/messages?language={lang}").json()
        result = next(m for m in thread if m["template_id"] == "result_raised")
        assert "152/96" in result["text"] and "131/83" not in result["text"], lang


def test_language_rerender_keeps_stored_text_when_template_cannot_render(api):
    """The plan messages need an action slot the thread route does not have. The stored text must survive, not become English."""
    cid = drive_khalid(api, "IN_CARE")
    assert api.act("patient_auh", cid, "plan_checkin", {"status": "missed"}).status_code == 200
    stored = {m["id"]: m for m in api.get("patient_auh", "/api/my/messages").json()}
    for lang in ("ar", "fr"):
        for m in api.get("patient_auh", f"/api/my/messages?language={lang}").json():
            if m["template_id"] in ("no_blame_checkin", "plan_smaller"):
                assert m["text"] and "It is fine that last week" not in m["text"] and m["text"] != "This week's action is smaller: "
                assert m["text"] == stored[m["id"]]["text"] or m["language"] == lang
