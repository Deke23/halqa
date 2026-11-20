"""Hardening pass: severe SMS, server-side drafts, one send function with consent, consent purposes, demo flag,
data minimisation, step reminders, time zones, tick logging, database audit triggers, message language and slots,
teach-back structure, display names."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import engine
from app.api import message_slots, wording_port
from app.api.regions import REGIONS, is_stop_keyword, tz_of
from app.db.models import Case, CaseEvent, Message, MessageDraft, Patient, Task, User
from app.engine.types import ConfirmationStatus, ReadingData, ReadingSource
from tests.conftest import add_hbpm_week, correct_answer, drive_khalid, iso, scenario_id, utc_now

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def events_of(app, case_id: int, type_: str | None = None) -> list[CaseEvent]:
    with app.state.db.session() as s:
        q = select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id)
        if type_:
            q = q.where(CaseEvent.type == type_)
        return list(s.scalars(q))


def messages_out(app, case_id: int) -> list[Message]:
    with app.state.db.session() as s:
        return list(s.scalars(select(Message).where(Message.case_id == case_id, Message.direction == "OUT").order_by(Message.id)))


def open_tasks(app, case_id: int, type_: str) -> list[Task]:
    with app.state.db.session() as s:
        return list(s.scalars(select(Task).where(Task.case_id == case_id, Task.type == type_, Task.status == "OPEN")))


def reply(api, persona: str, text_: str) -> list[dict]:
    r = api.post(persona, "/api/my/messages/reply", {"text": text_})
    assert r.status_code == 200, r.text
    return r.json()


def ack_by_sms(api, persona: str = "patient_yde") -> None:
    """The whole acknowledgement by replies: result read, no warning symptom, correct teach-back answer (B)."""
    reply(api, persona, "1")
    reply(api, persona, "2")
    reply(api, persona, "B")


# ---------------------------------------------------------------- 1. severe reading by SMS and the red-flag question


def test_severe_sms_reading_gets_the_urgent_template_with_the_emergency_instruction(api, app):
    cid = api.case_id("patient_yde")
    ack_by_sms(api)
    thread = reply(api, "patient_yde", "190/115")
    last = thread[-1]
    assert last["template_id"] == "result_severe" and last["language"] == "fr" and last["channel"] == "SMS"
    assert "190/115" in last["text"] and "urgences" in last["text"]  # the Cameroon instruction, no phone number
    assert "Nous avons bien reçu" not in last["text"]
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["urgent"] is True and d["severity"] == "SEVERE" and d["flags"]["urgent_review_pending"]
    assert api.get("nurse_yde", "/api/cases?queue=urgent").json()["cases"][0]["id"] == cid


def test_raised_sms_reading_still_gets_the_plain_acknowledgement(api):
    ack_by_sms(api)
    thread = reply(api, "patient_yde", "150/95")
    assert thread[-1]["template_id"] == "reply_received"


def test_phone_thread_asks_the_red_flag_question_and_yes_is_urgent_at_once(api, app):
    cid = api.case_id("patient_yde")
    thread = reply(api, "patient_yde", "1")  # result read
    assert thread[-1]["template_id"] == "red_flag_check" and "1" in thread[-1]["text"] and "2" in thread[-1]["text"]
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == "NOTIFIED"  # not acknowledged before teach-back
    before = len(messages_out(app, cid))
    thread = reply(api, "patient_yde", "1")  # yes, a warning symptom now
    assert len(messages_out(app, cid)) == before + 1  # exactly one outbound message: the emergency instruction
    assert last(thread)["template_id"] == "urgent_red_flags_sms" and "urgences" in last(thread)["text"]
    assert "appellera" in last(thread)["text"] and "1" in last(thread)["text"] and len(last(thread)["text"]) <= 160
    assert not [m for m in thread if m["template_id"] == "teach_back_question"]  # nothing routine follows emergency advice
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["urgent"] is True and d["urgent_reason"] == "RED_FLAG" and d["state"] == "NOTIFIED"
    assert [e.type for e in events_of(app, cid)].count("RED_FLAG_REPORTED") == 1
    assert len(open_tasks(app, cid, "COORDINATOR_CALL")) == 1
    assert [(v["reply"], v["meaning_key"]) for v in last(thread)["valid_replies"]] == [("1", "reply.continue"), ("0", "reply.call_me")]
    assert api.get("nurse_yde", "/api/cases?queue=urgent").json()["cases"][0]["id"] == cid
    # while waiting, a letter is not an answer; 0 does not create a second call task
    assert last(reply(api, "patient_yde", "B"))["template_id"] == "reply_not_understood"
    reply(api, "patient_yde", "0")
    assert len(open_tasks(app, cid, "COORDINATOR_CALL")) == 1
    thread = reply(api, "patient_yde", "1")  # the later 1 carries on
    assert last(thread)["template_id"] == "teach_back_question"
    reply(api, "patient_yde", "B")
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == "ACKNOWLEDGED"
    assert len(open_tasks(app, cid, "COORDINATOR_CALL")) == 1


def test_phone_red_flag_no_goes_on_to_teach_back_without_urgency(api):
    cid = api.case_id("patient_yde")
    reply(api, "patient_yde", "1")
    thread = reply(api, "patient_yde", "2")
    assert thread[-1]["template_id"] == "teach_back_question"
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["state"] == "NOTIFIED" and d["urgent"] is False


def test_app_path_and_phone_path_flag_red_flags_the_same_way(api, app):
    app_case = api.case_id("patient_auh")
    r = api.act("patient_auh", app_case, "acknowledge",
                {"teach_back_answer": correct_answer(api.my_case("patient_auh")), "red_flags": ["chest_pain"], "confidence": 3})
    assert r.json()["feedback"]["code"] == "RED_FLAG_EMERGENCY" and r.json()["urgent"] is True
    yde_case = api.case_id("patient_yde")
    reply(api, "patient_yde", "1")
    reply(api, "patient_yde", "1")
    for cid in (app_case, yde_case):
        assert [e.type for e in events_of(app, cid)].count("RED_FLAG_REPORTED") == 1
        assert [e.type for e in events_of(app, cid)].count("URGENT_FLAGGED") == 1


# ---------------------------------------------------------------- 2. the send endpoint does not trust the client


def draft(api, persona: str, cid: int, template_id: str = "reminder_ack", language: str = "en", **extra) -> dict:
    r = api.post(persona, f"/api/cases/{cid}/messages/draft", {"template_id": template_id, "language": language, **extra})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def ai_provider(monkeypatch):
    """A fake provider so the AI re-worded path can be tested without a network."""
    from app.wording import providers

    monkeypatch.setenv("WORDING_PROVIDER", "anthropic")
    monkeypatch.setattr(providers, "call_provider", lambda provider, system, text_: text_.replace("Hello", "Hi", 1))


def test_send_refuses_free_text_and_client_supplied_drafts(api, app):
    cid = scenario_id(app, "unowned")
    d = draft(api, "coordinator_auh", cid)
    for body in ({"draft": d}, {"draft": {**d, "text": "Pay me now", "source": "TEMPLATE"}}, {"text": "Free text", "source": "TEMPLATE"},
                 {"draft_id": d["id"], "text": "Free text", "source": "TEMPLATE"}, {}):
        r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", body)
        assert r.status_code == 422, body
    assert not [m for m in messages_out(app, cid) if m.draft_id == d["id"]]


def test_send_uses_the_server_copy_not_the_stored_text(api, app):
    cid = scenario_id(app, "unowned")
    d = draft(api, "coordinator_auh", cid)
    with app.state.db.session() as s:  # someone edits the stored draft text directly
        row = s.get(MessageDraft, d["id"])
        row.text = "Send your bank details to this number"
        s.commit()
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"]})
    assert r.status_code == 200 and r.json()["message"]["text"] == d["text"] and "bank" not in r.json()["message"]["text"]
    assert r.json()["message"]["source"] == "TEMPLATE"


def test_draft_unknown_other_case_and_double_send(api, app):
    cid = scenario_id(app, "unowned")
    other = scenario_id(app, "overdue_ack")
    d = draft(api, "coordinator_auh", cid)
    assert api.post("coordinator_auh", f"/api/cases/{other}/messages/send", {"draft_id": d["id"]}).status_code == 404
    assert api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": 99999}).status_code == 404
    assert api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"]}).status_code == 200
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"]})
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_SENT"
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/draft", {"template_id": "made_up", "language": "en"})
    assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_TEMPLATE"
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/draft", {"template_id": "weekly_action", "language": "en"})
    assert r.status_code == 422 and r.json()["code"] == "TEMPLATE_UNAVAILABLE"  # needs an action the case does not have
    assert api.post("patient_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"]}).status_code == 403


def test_ai_reworded_draft_needs_explicit_approval_and_the_audit_records_it(api, app, ai_provider):
    cid = scenario_id(app, "unowned")
    d = draft(api, "coordinator_auh", cid, tone="warm")
    assert d["source"] == "AI_REWORDED" and d["text"].startswith("Hi ") and d["validation"]["passed"] is True
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"]})
    assert r.status_code == 409 and r.json()["code"] == "APPROVAL_REQUIRED"
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"], "approve": False})
    assert r.status_code == 409
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"], "approve": True})
    assert r.status_code == 200
    msg = r.json()["message"]
    assert msg["source"] == "AI_REWORDED" and msg["approved_by_name"].startswith("Mariam") and msg["approved_by_person"]["name"] == "Mariam"
    sent = [e for e in events_of(app, cid, "MESSAGE_SENT") if e.payload.get("draft_id") == d["id"]][0]
    assert sent.payload["approved_by_user_id"] == sent.actor_user_id
    assert sent.payload["validation"]["passed"] is True and sent.payload["validation"]["checks"]
    assert sent.payload["source"] == "AI_REWORDED"


def test_ai_reworded_text_is_revalidated_at_send(api, app, ai_provider):
    cid = scenario_id(app, "unowned")
    d = draft(api, "coordinator_auh", cid, tone="warm")
    with app.state.db.session() as s:  # the stored re-worded text is changed after validation
        row = s.get(MessageDraft, d["id"])
        row.text = row.text + " Your reading is 250 now."
        s.commit()
    r = api.post("coordinator_auh", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"], "approve": True})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_FAILED"
    assert not [m for m in messages_out(app, cid) if m.draft_id == d["id"]]


# ---------------------------------------------------------------- 3. one send function, channel consent


def test_every_outbound_message_is_stored_by_the_single_send_function():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        if re.search(r"\bMessage\(", src) and path.name not in ("models.py", "core.py"):
            offenders.append(path.name)
    assert offenders == []
    core = (APP_DIR / "api" / "core.py").read_text(encoding="utf-8")
    assert core.count("Message(") == 1  # add_message, called by send_message for OUT rows and by the reply handler for IN rows


def test_withdrawn_channel_suppresses_reminders_and_creates_one_task(api, app):
    cid = api.case_id("patient_yde")
    for channel in ("SMS", "APP"):  # no agreed channel remains at all
        assert api.act("patient_yde", cid, "update_consent", {"purpose": "messaging_channel", "channel": channel, "granted": False}).status_code == 200
    before = len(messages_out(app, cid))
    for hours in (25, 30, 60):  # reminder, second channel, more reminders over three days
        assert api.post("nurse_yde", "/api/demo/clock/advance", {"hours": hours}).status_code == 200
    assert len(messages_out(app, cid)) == before  # nothing was sent
    suppressed = events_of(app, cid, "MESSAGE_SUPPRESSED")
    assert suppressed and all(e.payload["consent_purpose"] in ("messaging_channel",) for e in suppressed)
    assert len(open_tasks(app, cid, "CONTACT_OTHER_ROUTE")) == 1
    task = api.get("nurse_yde", f"/api/cases/{cid}").json()["tasks"]
    assert [t["title_key"] for t in task if t["type"] == "CONTACT_OTHER_ROUTE"] == ["contact_by_another_agreed_route"]


def test_second_channel_without_consent_is_skipped_and_recorded_without_an_extra_task(api, app):
    cid = scenario_id(app, "overdue_ack")  # an app patient who never agreed to SMS, 5 days late
    sms = [e for e in events_of(app, cid, "MESSAGE_SUPPRESSED") if e.payload["channel"] == "SMS"]
    assert len(sms) == 1 and sms[0].payload["skipped_to_next_stage"] is True
    assert not [m for m in messages_out(app, cid) if m.channel == "SMS"]
    assert not open_tasks(app, cid, "CONTACT_OTHER_ROUTE")  # the app channel is still agreed
    assert open_tasks(app, cid, "COORDINATOR_CALL")  # the protocol went on to the coordinator call


def test_seeded_people_have_explicit_channel_consent_with_a_few_without_sms(app):
    from app.api.core import consented_channels

    with app.state.db.session() as s:
        patients = list(s.scalars(select(Patient)))
        without_sms = [p.ref for p in patients if "SMS" not in consented_channels(s, p.id)]
        assert 2 <= len(without_sms) <= 3 and all(r.startswith("SYN-AUH") for r in without_sms)
        assert all("APP" in consented_channels(s, p.id) for p in patients)
        personas = [p for p in patients if p.ref in ("KHALID-AUH", "JEANPAUL-YDE")]
        assert all({"APP", "SMS"} <= consented_channels(s, p.id) for p in personas)


def test_withdrawing_the_only_remaining_channel_creates_the_task_once(api, app):
    cid = api.case_id("patient_yde")
    api.act("patient_yde", cid, "update_consent", {"purpose": "messaging_channel", "channel": "SMS", "granted": False})
    assert not open_tasks(app, cid, "CONTACT_OTHER_ROUTE")  # the app is still agreed
    api.act("patient_yde", cid, "update_consent", {"purpose": "messaging_channel", "channel": "APP", "granted": False})
    assert len(open_tasks(app, cid, "CONTACT_OTHER_ROUTE")) == 1


def test_stop_withdraws_the_channel_and_gets_one_final_confirmation(api, app):
    cid = api.case_id("patient_yde")
    thread = reply(api, "patient_yde", "STOP")
    assert thread[-1]["template_id"] == "stop_confirmed" and thread[-1]["language"] == "fr" and "plus de messages" in thread[-1]["text"]
    me = api.my_case("patient_yde")
    assert any(c["purpose"] == "messaging_channel" and c["channel"] == "SMS" and not c["granted"] for c in me["consents"])
    n = len(messages_out(app, cid))
    reply(api, "patient_yde", "stop")  # a repeat gets no second confirmation
    assert len(messages_out(app, cid)) == n
    assert api.post("nurse_yde", "/api/demo/clock/advance", {"hours": 30}).status_code == 200
    assert len(messages_out(app, cid)) == n  # and no reminder follows


@pytest.mark.parametrize("word", ["STOP", "stop", "Arrêt", "ARRET", "arreter", "توقف", "إيقاف", " Stop. "])
def test_stop_words_in_three_languages(word):
    assert is_stop_keyword(word)


@pytest.mark.parametrize("word", ["stopping", "1", "bonjour", "150/95", ""])
def test_other_text_is_not_a_stop_word(word):
    assert not is_stop_keyword(word)


def test_staff_send_to_a_withdrawn_channel_is_refused_and_recorded(api, app):
    cid = api.case_id("patient_yde")
    api.act("patient_yde", cid, "update_consent", {"purpose": "messaging_channel", "channel": "SMS", "granted": False})
    d = draft(api, "nurse_yde", cid, language="fr")
    r = api.post("nurse_yde", f"/api/cases/{cid}/messages/send", {"draft_id": d["id"]})
    assert r.status_code == 409 and r.json()["code"] == "CONSENT_WITHDRAWN"
    assert any(e.payload["kind"] == "STAFF" for e in events_of(app, cid, "MESSAGE_SUPPRESSED"))


# ---------------------------------------------------------------- 4. the other consent purposes do something


def test_withdrawing_care_coordination_stops_automated_messages_and_asks_a_clinician(api, app):
    cid = api.case_id("patient_yde")
    assert api.act("patient_yde", cid, "update_consent", {"purpose": "care_coordination", "granted": False}).status_code == 200
    before = len(messages_out(app, cid))
    api.post("nurse_yde", "/api/demo/clock/advance", {"hours": 24 * 6})
    assert len(messages_out(app, cid)) == before
    on_sms = [e for e in events_of(app, cid, "MESSAGE_SUPPRESSED") if e.payload["channel"] == "SMS"]
    assert on_sms and {e.payload["consent_purpose"] for e in on_sms} == {"care_coordination"}
    d = api.get("clinician_yde", f"/api/cases/{cid}").json()
    decision = [t for t in d["tasks"] if t["type"] == "CONSENT_DECISION"]
    assert len(decision) == 1 and decision[0]["owner_role"] == "clinician" and decision[0]["status"] == "OPEN"
    assert d["state"] != "CLOSED" and d["flags"]["care_coordination_withdrawn"] and d["suggested_closure_type"] == "PATIENT_DECLINED"
    assert not [t for t in d["tasks"] if t["type"] == "COORDINATOR_CALL"]  # no call task for a patient who withdrew
    row = [c for c in api.get("nurse_yde", "/api/cases").json()["cases"] if c["id"] == cid][0]
    assert row["reason_code"] == "CARE_COORDINATION_WITHDRAWN"
    # nothing closes by itself; only the clinician may close, with PATIENT_DECLINED
    closed = api.act("clinician_yde", cid, "close", {"evidence_type": "PATIENT_DECLINED", "decision_note": "Patient withdrew care coordination"})
    assert closed.status_code == 200 and closed.json()["state"] == "CLOSED"
    assert not open_tasks(app, cid, "CONSENT_DECISION")


def test_granting_care_coordination_again_clears_the_decision_task(api, app):
    cid = api.case_id("patient_yde")
    api.act("patient_yde", cid, "update_consent", {"purpose": "care_coordination", "granted": False})
    api.act("patient_yde", cid, "update_consent", {"purpose": "care_coordination", "granted": True})
    assert not open_tasks(app, cid, "CONSENT_DECISION")
    assert api.get("clinician_yde", f"/api/cases/{cid}").json()["flags"]["care_coordination_withdrawn"] is False


def test_withdrawing_lifestyle_programme_stops_a_running_plan(api, app):
    cid = drive_khalid(api, "IN_CARE")
    assert api.my_case("patient_auh")["plan_active"] is True
    assert api.act("patient_auh", cid, "update_consent", {"purpose": "lifestyle_programme", "granted": False}).status_code == 200
    d = api.my_case("patient_auh")
    assert d["plan_active"] is False and "plan_checkin" not in d["allowed_actions"]
    weeks = len(d["plan"])
    r = api.act("patient_auh", cid, "plan_checkin", {"status": "done"})
    assert r.status_code == 409 and r.json()["code"] == "PLAN_STOPPED"
    sent = len(messages_out(app, cid))
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 24 * 20})  # three weeks pass
    d = api.my_case("patient_auh")
    assert len(d["plan"]) == weeks and not [w for w in d["plan"] if w["status"]]  # no missed week recorded, no new week
    assert not [m for m in messages_out(app, cid) if m.template_id in ("weekly_action", "no_blame_checkin", "plan_smaller")]
    assert len(messages_out(app, cid)) >= sent
    # granting it again restarts the open week
    api.act("patient_auh", cid, "update_consent", {"purpose": "lifestyle_programme", "granted": True})
    d = api.my_case("patient_auh")
    assert d["plan_active"] is True and "plan_checkin" in d["allowed_actions"]
    assert api.act("patient_auh", cid, "plan_checkin", {"status": "done"}).status_code == 200


def test_dashboard_leaves_out_people_who_have_not_opted_in(api):
    def n(name: str) -> int:
        groups = api.get("analyst", "/api/dashboard/live").json()["groups"]
        return next(m for m in groups[0]["measures"] if m["name"] == name)["n"]

    before = n("time_to_notification_h")
    assert api.act("patient_auh", api.case_id("patient_auh"), "update_consent", {"purpose": "research_aggregate", "granted": False}).status_code == 200
    assert n("time_to_notification_h") == before - 1
    api.act("patient_auh", api.case_id("patient_auh"), "update_consent", {"purpose": "research_aggregate", "granted": True})
    assert n("time_to_notification_h") == before


def test_new_intake_people_are_not_counted_until_they_opt_in(api):
    def total(split: str = "none") -> int:
        groups = api.get("analyst", f"/api/dashboard/live?split={split}").json()["groups"]
        return sum(next(m for m in g["measures"] if m["name"] == "time_to_notification_h")["n"] for g in groups)

    before = total()
    for i in range(3):
        r = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": f"NEW-{i}", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                              "readings": [{"systolic": 150, "diastolic": 95}]})
        assert r.json()["opened"]
    assert total() == before


# ---------------------------------------------------------------- 5. demo controls behind a flag


def test_demo_mode_default_is_on_and_exposed(api):
    assert api.client.get("/api/config").json()["demo_mode"] is True


def test_demo_mode_off_disables_every_demo_control(api, monkeypatch):
    staff_headers, analyst_headers = api.as_("coordinator_auh"), api.as_("analyst")  # tokens issued while the demo was on
    monkeypatch.setenv("DEMO_MODE", "false")
    assert api.client.get("/api/config").json()["demo_mode"] is False
    r = api.client.post("/api/auth/guest", json={"persona": "patient_auh"})
    assert r.status_code == 403 and r.json()["code"] == "DEMO_MODE_OFF"
    assert api.client.post("/api/demo/clock/advance", headers=staff_headers, json={"hours": 1}).status_code == 403
    assert api.client.post("/api/demo/reset", headers=analyst_headers).status_code == 403
    r = api.client.post("/api/intake/result", headers=staff_headers, json={
        "patient_ref": "X", "source_system": "IFHAS_SCREENING", "region": "AUH", "readings": [{"systolic": 185, "diastolic": 115}]})
    assert r.status_code == 403 and r.json()["code"] == "DEMO_MODE_OFF"
    assert api.client.get("/api/cases", headers=staff_headers).status_code == 200  # the real app keeps working


def test_reset_needs_staff_or_analyst_and_clock_advance_any_signed_in_guest(api):
    assert api.client.post("/api/demo/reset").status_code == 401
    assert api.post("patient_auh", "/api/demo/reset").status_code == 403
    assert api.post("patient_auh", "/api/demo/clock/advance", {"hours": 24 * 7}).status_code == 200  # the "skip a week" shortcut
    assert api.client.post("/api/demo/clock/advance", json={"hours": 1}).status_code == 401
    assert api.post("coordinator_auh", "/api/demo/reset").status_code == 200
    api._tokens.clear()
    assert api.post("analyst", "/api/demo/reset").status_code == 200


# ---------------------------------------------------------------- 6. data minimisation for coordinators


def closed_with_note_ids(app) -> list[int]:
    with app.state.db.session() as s:
        return list(s.scalars(select(Case.id).where(Case.closure_decision_note.is_not(None))))


def test_coordinator_does_not_get_closure_visit_urgent_or_econsult_notes(api, app):
    note = "Patient declined further follow-up after discussion with the clinician"
    cid = closed_with_note_ids(app)[0]
    staff = api.get("clinician_yde", f"/api/cases/{cid}").json()
    coord = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert staff["closure"]["decision_note"] == note
    assert coord["closure"]["decision_note"] is None and coord["closure"]["evidence_type"] and coord["closure"]["closed_by_name"]
    closed_event = [e for e in coord["timeline"] if e["type"] == "CASE_CLOSED"][0]
    assert closed_event["reason"] is None and closed_event["actor_name"] and closed_event["at"]
    assert note not in api.get("nurse_yde", f"/api/cases/{cid}").text

    # visit note and urgent review note
    visit_note = "Started low dose treatment, review in four weeks"
    k = drive_khalid(api, "APPOINTMENT_BOOKED")
    api.act("clinician_specialist", k, "record_visit", {"outcome": "TREATMENT_STARTED", "note": visit_note})
    assert visit_note in api.get("clinician_pcp", f"/api/cases/{k}").text
    assert visit_note not in api.get("coordinator_auh", f"/api/cases/{k}").text
    severe = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "DEMO-SEVERE", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                                "readings": [{"systolic": 185, "diastolic": 115}]}).json()["case_id"]
    urgent_note = "Phoned the patient, advised same day attendance"
    assert api.act("clinician_pcp", severe, "complete_urgent_review", {"note": urgent_note}).status_code == 200
    assert urgent_note in api.get("clinician_pcp", f"/api/cases/{severe}").text
    coordinator_view = api.get("coordinator_auh", f"/api/cases/{severe}")
    assert urgent_note not in coordinator_view.text
    done = [e for e in coordinator_view.json()["timeline"] if e["type"] == "URGENT_REVIEW_COMPLETED"][0]
    assert done["reason"] is None and done["actor_person"]["name"] == "Dr Sara"

    # e-consult content stays with clinicians
    econ = scenario_id(app, "econsult_open")
    assert "obstetrics" in api.get("clinician_pcp", f"/api/cases/{econ}").text
    assert "obstetrics" not in api.get("coordinator_auh", f"/api/cases/{econ}").text.lower()


def test_fhir_bundle_is_clinician_only(api, app):
    cid = scenario_id(app, "unowned")
    assert api.get("clinician_pcp", f"/api/cases/{cid}/fhir").status_code == 200
    for persona in ("coordinator_auh", "analyst", "patient_auh"):
        assert api.get(persona, f"/api/cases/{cid}/fhir").status_code == 403


def test_queue_rows_carry_everything_the_list_needs(api, app):
    rows = {r["id"]: r for r in api.get("coordinator_auh", "/api/cases").json()["cases"]}
    rejected = rows[scenario_id(app, "rejected_referral")]
    assert rejected["reason_code"] == "REFERRAL_REJECTED" and rejected["rejection_reason"] == "Wrong clinic, needs nephrology review"
    assert "nephrology" in rejected["reason_text"] and re.fullmatch(r"\d\d(-\d\d|\+)", rejected["age_band"])
    overdue = rows[scenario_id(app, "overdue_ack")]
    assert overdue["last_contact_attempt"] and overdue["last_contact_attempt_at"] and overdue["urgent"] is False
    assert all("age_band" in r and "reason_code" in r and "reason_text" in r and "urgent" in r for r in rows.values())
    severe = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "SEV", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                                "readings": [{"systolic": 185, "diastolic": 115}]}).json()["case_id"]
    row = [r for r in api.get("coordinator_auh", "/api/cases?queue=urgent").json()["cases"] if r["id"] == severe][0]
    assert row["urgent"] is True and row["reason_code"] == "URGENT_SEVERE"
    assert "decision_note" not in str(rows)


def test_reading_a_list_writes_no_case_viewed_events_but_the_detail_does(api, app):
    def viewed() -> int:
        with app.state.db.session() as s:
            return len(list(s.scalars(select(CaseEvent).where(CaseEvent.type == "CASE_VIEWED"))))

    base = viewed()
    for q in ("all", "overdue", "unowned"):
        assert api.get("coordinator_auh", f"/api/cases?queue={q}").status_code == 200
    assert viewed() == base
    cid = scenario_id(app, "unowned")
    api.get("coordinator_auh", f"/api/cases/{cid}")
    assert viewed() == base + 1


# ---------------------------------------------------------------- 7. step-specific reminders


def last_out(app, cid: int) -> Message:
    return messages_out(app, cid)[-1]


def test_reminder_wording_matches_the_late_step_and_the_patient_language(api, app):
    cid = scenario_id(app, "overdue_ack")
    reminders = [m for m in messages_out(app, cid) if m.template_id == "reminder_ack"]
    assert reminders and reminders[0].language in ("ar", "en") and reminders[0].slots

    k = drive_khalid(api, "ACKNOWLEDGED")
    api.act("patient_auh", k, "choose_confirmation", {"method": "HBPM"})
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 26})
    m = last_out(app, k)
    assert m.template_id == "reminder_home_readings" and m.language == "ar" and re.search("[؀-ۿ]", m.text) and "ضغط" in m.text
    with app.state.db.session() as s:
        patient = s.get(Patient, s.get(Case, k).patient_id)
        assert patient.language == "ar"

    # booking step: a referral accepted, no visit time chosen yet
    k2 = None
    api.post("analyst", "/api/demo/reset")
    api._tokens.clear()
    k2 = drive_khalid(api, "REFERRED")
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 26})
    m = last_out(app, k2)
    assert m.template_id == "reminder_booking" and m.language == "ar" and "موعد" in m.text


def test_reminder_templates_exist_in_three_languages_and_sms_variants():
    for tid in ("reminder_ack", "reminder_home_readings", "reminder_booking", "appointment_reminder"):
        for suffix in ("", "_sms"):
            tpl = wording_port._wording().get_template(tid + suffix)
            assert set(tpl["text"]) == {"en", "ar", "fr"}
    assert wording_port.render("reminder_home_readings", "fr", {"name": "Eric", "due_date": "3 mars"}, "SMS").template_id == "reminder_home_readings_sms"


def test_appointment_reminder_is_sent_once_in_the_last_day_before_the_visit(api, app):
    k = drive_khalid(api, "APPOINTMENT_BOOKED")
    assert not [m for m in messages_out(app, k) if m.template_id == "appointment_reminder"]
    detail = api.my_case("patient_auh")
    starts = datetime.fromisoformat(detail["appointment"]["starts_at"])
    hours_to_go = (starts - utc_now()).total_seconds() / 3600
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": hours_to_go - 20})
    api.post("coordinator_auh", "/api/demo/clock/advance", {"hours": 1})
    sent = [m for m in messages_out(app, k) if m.template_id == "appointment_reminder"]
    assert len(sent) == 1 and sent[0].language == "ar"


# ---------------------------------------------------------------- 8. time zones


def reading(day: int, hour: int, minute: int = 0, source: ReadingSource = ReadingSource.HOME_CUFF) -> ReadingData:
    return ReadingData(150, 95, datetime(2026, 3, day, hour, minute, tzinfo=timezone.utc), source)


def test_region_config_has_time_zones():
    assert REGIONS["AUH"]["timezone"] == "Asia/Dubai" and REGIONS["YDE"]["timezone"] == "Africa/Douala"
    assert tz_of("AUH").utcoffset(datetime(2026, 3, 1)).total_seconds() == 4 * 3600
    assert tz_of("YDE").utcoffset(datetime(2026, 3, 1)).total_seconds() == 3600


def test_hbpm_days_are_local_days_not_utc_days():
    # 19:30 and 20:30 UTC are 23:30 and 00:30 in Abu Dhabi: two readings on one UTC day, but on two local days.
    readings = [r for d in range(1, 5) for r in (reading(d, 19, 30), reading(d, 20, 30))]
    utc = engine.evaluate_confirmation(engine.ConfirmationMethod.HBPM, readings)
    assert utc.status is ConfirmationStatus.CONFIRMED_RAISED and utc.days_with_enough_readings == 4
    local = engine.evaluate_confirmation(engine.ConfirmationMethod.HBPM, readings, tz_of("AUH"))
    assert local.status is ConfirmationStatus.INSUFFICIENT and local.days_with_enough_readings == 3  # the end days hold one reading
    # the same instants in Yaounde (UTC+1) are 20:30 and 21:30: one local day, so four days still count
    yde = engine.evaluate_confirmation(engine.ConfirmationMethod.HBPM, readings, tz_of("YDE"))
    assert yde.status is ConfirmationStatus.CONFIRMED_RAISED and yde.days_with_enough_readings == 4
    # 21:00 and 23:30 UTC on one UTC day are 01:00 and 03:30 the next day in Abu Dhabi: one local day each
    same_local = [r for d in range(1, 6) for r in (reading(d, 21), reading(d, 23, 30))]
    assert engine.evaluate_confirmation(engine.ConfirmationMethod.HBPM, same_local, tz_of("AUH")).status is ConfirmationStatus.CONFIRMED_RAISED


def test_abpm_daytime_window_is_local_time():
    readings = [reading(1, h, source=ReadingSource.ABPM) for h in range(3, 17)]  # 14 readings, 03:00 to 16:00 UTC
    assert engine.evaluate_confirmation(engine.ConfirmationMethod.ABPM, readings).status is ConfirmationStatus.INSUFFICIENT  # UTC window: 10 inside
    assert engine.evaluate_confirmation(engine.ConfirmationMethod.ABPM, readings, tz_of("AUH")).status is ConfirmationStatus.CONFIRMED_RAISED
    edge = [reading(1, 2, 59, ReadingSource.ABPM)] + readings[1:]  # 02:59 UTC is 06:59 in Abu Dhabi: before the 07:00 window start
    assert engine.evaluate_confirmation(engine.ConfirmationMethod.ABPM, edge, tz_of("AUH")).status is ConfirmationStatus.INSUFFICIENT
    late = [reading(1, 18, 0, ReadingSource.ABPM)] + readings[:-1]  # 18:00 UTC is 22:00 in Abu Dhabi: the window end is exclusive
    assert engine.evaluate_confirmation(engine.ConfirmationMethod.ABPM, late, tz_of("AUH")).status is ConfirmationStatus.INSUFFICIENT


def test_api_groups_home_readings_by_the_regions_local_day(api):
    cid = api.case_id("patient_auh")
    case = api.my_case("patient_auh")
    api.act("patient_auh", cid, "acknowledge", {"teach_back_answer": correct_answer(case), "red_flags": [], "confidence": 4})
    api.act("patient_auh", cid, "choose_confirmation", {"method": "HBPM"})
    base = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
    for d in range(4):  # 19:30 and 20:30 UTC are 23:30 and 00:30 in Abu Dhabi: four UTC days, only three local days with two readings
        for hour in (19, 20):
            at = base + timedelta(days=d, hours=hour, minutes=30)
            assert api.act("patient_auh", cid, "add_reading", {"systolic": 150, "diastolic": 95, "taken_at": iso(at), "source": "HOME_CUFF"}).status_code == 200
    assert api.my_case("patient_auh")["confirmation"]["status"] == "INSUFFICIENT"


# ---------------------------------------------------------------- 9. the background tick


def test_tick_logs_the_traceback_and_keeps_running(app, monkeypatch, caplog):
    from app import main

    calls = {"n": 0}

    def flaky(db, now):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("tick went wrong")
        return 0

    monkeypatch.setattr(main, "tick_all", flaky)

    async def run() -> None:
        task = asyncio.create_task(main.tick_loop(app, 0.01))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if calls["n"] >= 2:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    with caplog.at_level(logging.ERROR, logger="app.tick"):
        asyncio.run(run())
    assert calls["n"] >= 2  # it ran again after the failure
    record = [r for r in caplog.records if r.name == "app.tick"][0]
    assert record.exc_info and "tick went wrong" in "".join(__import__("traceback").format_exception(*record.exc_info))


# ---------------------------------------------------------------- 10. audit log in the database


def test_database_refuses_raw_update_and_delete_on_case_events(app):
    cid = scenario_id(app, "unowned")
    with app.state.db.session() as s:
        n = s.execute(text("SELECT COUNT(*) FROM case_events")).scalar_one()
        with pytest.raises(DBAPIError, match="append-only"):
            s.execute(text("UPDATE case_events SET reason = 'edited' WHERE case_id = :c"), {"c": cid})
        s.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            s.execute(text("DELETE FROM case_events WHERE case_id = :c"), {"c": cid})
        s.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            s.execute(text("DELETE FROM case_events"))
        s.rollback()
        assert s.execute(text("SELECT COUNT(*) FROM case_events")).scalar_one() == n
        s.execute(text("INSERT INTO case_events (case_id, at, actor, actor_role, type, payload) "
                       "VALUES (:c, '2026-01-01 00:00:00', 'system', 'system', 'CASE_VIEWED', '{}')"), {"c": cid})
        s.commit()  # appending still works
        assert s.execute(text("SELECT COUNT(*) FROM case_events")).scalar_one() == n + 1


def test_reset_still_works_with_the_triggers_and_reinstalls_them(api, app):
    assert api.post("analyst", "/api/demo/reset").status_code == 200
    with app.state.db.session() as s:
        names = {r[0] for r in s.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'"))}
        assert {"case_events_no_update", "case_events_no_delete"} <= names
        with pytest.raises(DBAPIError):
            s.execute(text("UPDATE case_events SET reason = 'x'"))


def test_an_older_database_gets_the_new_columns(tmp_path):
    from sqlalchemy import create_engine

    from app.db import Database

    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    old = create_engine(url)
    with old.begin() as c:
        c.exec_driver_sql("CREATE TABLE messages (id INTEGER PRIMARY KEY, case_id INTEGER, direction TEXT, channel TEXT, language TEXT, text TEXT, "
                          "template_id TEXT, template_version TEXT, source TEXT, sender_user_id INTEGER, approved_by_user_id INTEGER, created_at DATETIME)")
        c.exec_driver_sql("CREATE TABLE cases (id INTEGER PRIMARY KEY, patient_id INTEGER, region TEXT)")
    db = Database(url)
    db.create_all()
    with db.engine.connect() as c:
        cols = {r[1] for r in c.exec_driver_sql("PRAGMA table_info(messages)")}
        case_cols = {r[1] for r in c.exec_driver_sql("PRAGMA table_info(cases)")}
    assert {"slots", "draft_id"} <= cols and {"care_coordination_withdrawn", "sms_prompt"} <= case_cols


# ---------------------------------------------------------------- 11. dates follow the message language and region clock


def test_localize_formats_dates_for_the_language_and_region_clock():
    neutral = {"due_at": "2026-03-01T21:30:00+00:00", "appointment_at": "2026-03-10T05:15:00+00:00", "name": "A", "reading": "150/95"}
    assert message_slots.localize(neutral, "en", "AUH")["due_date"] == "2 March"  # 01:30 on 2 March in Abu Dhabi
    assert message_slots.localize(neutral, "en", "YDE")["due_date"] == "1 March"  # 22:30 on 1 March in Yaounde
    assert message_slots.localize(neutral, "fr", "YDE")["due_date"] == "1 mars"
    ar = message_slots.localize(neutral, "ar", "AUH")
    assert ar["due_date"] == "2 مارس" and ar["appointment_time"] == "09:15" and ar["appointment_date"] == "10 مارس"
    assert ar["reading"] == "150/95" and re.fullmatch(r"[0-9: -]+", ar["appointment_time"] + ar["date"] + ar["time"])  # Latin digits


def test_english_draft_has_an_english_month_and_arabic_draft_an_arabic_one(api, app):
    cid = scenario_id(app, "unowned")  # an Arabic-speaking patient
    en = draft(api, "coordinator_auh", cid, language="en")["text"]
    ar = draft(api, "coordinator_auh", cid, language="ar")["text"]
    months_ar = message_slots._MONTHS["ar"]
    assert not any(m in en for m in months_ar) and any(m in en for m in message_slots._MONTHS["en"])
    assert any(m in ar for m in months_ar)


def test_a_re_rendered_message_keeps_the_slots_it_was_created_with(api, app):
    cid = api.case_id("patient_auh")
    with app.state.db.session() as s:
        first = s.scalars(select(Message).where(Message.case_id == cid, Message.template_id == "result_raised")).first()
        due = datetime.fromisoformat(first.slots["due_at"])
        assert first.slots["reading"] == "152/96"
    drive_khalid(api, "CONFIRMED")  # the next step and its due date move on, and home readings change the latest reading
    expected = message_slots.format_date(due.astimezone(tz_of("AUH")), "en")
    for lang in ("en", "fr"):
        thread = api.get("patient_auh", f"/api/my/messages?language={lang}").json()
        result = next(m for m in thread if m["template_id"] == "result_raised")
        assert "152/96" in result["text"]
    en = next(m for m in api.get("patient_auh", "/api/my/messages?language=en").json() if m["template_id"] == "result_raised")
    assert expected in en["text"]


# ---------------------------------------------------------------- 12. messages are stored in the patient's language


def test_seeded_messages_are_stored_in_the_patients_language_from_the_templates(app):
    with app.state.db.session() as s:
        rows = list(s.execute(select(Message, Patient).join(Case, Case.id == Message.case_id).join(Patient, Patient.id == Case.patient_id)
                              .where(Message.direction == "OUT")).all())
        assert rows
        for m, p in rows:
            assert m.language == p.language, (m.id, m.language, p.language)
            assert m.template_version != wording_port.FALLBACK_VERSION and m.slots
            if p.language == "ar":
                assert re.search("[؀-ۿ]", m.text), m.text
            if p.language == "fr":
                assert "Your " not in m.text


def test_system_messages_are_written_in_the_patients_language(api, app):
    k = drive_khalid(api, "REFERRED")
    texts = [m for m in messages_out(app, k) if m.template_id in ("referral_sent", "referral_accepted")]
    assert texts and all(m.language == "ar" and re.search("[؀-ۿ]", m.text) for m in texts)


@pytest.mark.parametrize("key", ["salt", "activity", "sleep", "home_bp_check"])
@pytest.mark.parametrize("size", ["full", "smaller", "smallest"])
def test_every_plan_action_has_text_in_three_languages(key, size):
    en, ar, fr = (wording_port.plan_text(key, size, lang) for lang in ("en", "ar", "fr"))
    assert en and ar and fr and len({en, ar, fr}) == 3
    assert re.search("[؀-ۿ]", ar) and not re.search("[؀-ۿ]", fr)
    assert wording_port.plan_text(key, size) == en


def test_plan_view_and_check_in_messages_use_the_patients_language(api, app):
    cid = drive_khalid(api, "IN_CARE")
    d = api.my_case("patient_auh")
    assert re.search("[؀-ۿ]", d["plan"][0]["default_text"])
    assert "salt" not in d["plan"][0]["default_text"].lower()
    en = api.get("patient_auh", "/api/my/case?language=en").json()["plan"][0]["default_text"]
    assert "salt" in en.lower()
    api.act("patient_auh", cid, "plan_checkin", {"status": "missed"})
    plan_msgs = [m for m in messages_out(app, cid) if m.template_id in ("no_blame_checkin", "plan_smaller")]
    assert plan_msgs and all(m.language == "ar" and re.search("[؀-ۿ]", m.text) for m in plan_msgs)
    thread_fr = api.get("patient_auh", "/api/my/messages?language=fr").json()
    smaller = next(m for m in thread_fr if m["template_id"] == "plan_smaller")
    assert "Marchez" in smaller["text"] or "salière" in smaller["text"] or "Goûtez" in smaller["text"]


# ---------------------------------------------------------------- 13. teach-back in the app


def test_app_teach_back_has_no_reply_sentence_and_is_structured(api):
    d = api.my_case("patient_auh")
    tb = d["teach_back"]
    assert tb["language"] == "ar" and len(tb["options"]) == 3 and tb["simpler"] and "152/96" in tb["question"]
    assert "اختيار" not in tb["question"] and "1" not in tb["question"].replace("152/96", "")
    en = api.get("patient_auh", "/api/my/case?language=en").json()["teach_back"]
    fr = api.get("patient_auh", "/api/my/case?language=fr").json()["teach_back"]
    assert en["language"] == "en" and "Reply" not in en["question"] and en["options"][1].startswith("It is a raised reading")
    assert fr["language"] == "fr" and "Répondez" not in fr["question"] and fr["simpler"] != en["simpler"]
    assert not any(o in en["question"] for o in en["options"])  # the options are not pasted into the text


def test_sms_teach_back_keeps_its_reply_sentence():
    app_q = wording_port.teach_back("en", {"reading": "152/96"}, app=True)
    sms_q = wording_port.teach_back("en", {"reading": "152/96"}, sms=True)
    assert "Reply" not in app_q["question"] and "Reply" in sms_q["question"]
    assert app_q["correct"] == sms_q["correct"] == 2


def test_the_app_thread_teach_back_message_has_no_reply_sentence(api, app):
    cid = api.case_id("patient_auh")
    msg = [m for m in messages_out(app, cid) if m.template_id == "teach_back_question"][0]
    assert "Reply" not in msg.text and "اختيار 1" not in msg.text and "\n1." not in msg.text


# ---------------------------------------------------------------- 14. display names


def test_people_come_with_separate_name_and_role(api, app):
    users = {u["persona"]: u for u in api.get("coordinator_auh", "/api/users").json()}
    nurse = users["nurse_yde"]
    assert nurse["name"] == "Clarisse (nurse coordinator)" and nurse["display_name"] == "Clarisse" and nurse["role_title"] == "nurse coordinator"
    assert api.get("coordinator_auh", "/api/me").json()["display_name"] == "Mariam"
    personas = {p["persona"]: p for p in api.client.get("/api/personas").json()}
    assert personas["clinician_pcp"]["display_name"] == "Dr Sara" and personas["clinician_pcp"]["role_title"] == "family medicine"
    assert personas["analyst"]["display_name"] == "Programme analyst"

    cid = api.case_id("patient_yde")
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["owner_name"] == "Clarisse (nurse coordinator)" and (d["owner_person"]["name"], d["owner_person"]["role"]) == ("Clarisse", "nurse coordinator")
    assert d["next_step"]["owner_person"]["name"] == "Clarisse"
    row = api.get("nurse_yde", "/api/cases").json()["cases"][0]
    assert row["owner_person"] is None or "(" not in row["owner_person"]["name"]
    assert any(e["actor_person"] and "(" not in e["actor_person"]["name"] for e in d["timeline"])
    assert all("(" not in (m["sender_person"] or {"name": ""})["name"] for m in d["messages"])

    econ = scenario_id(app, "econsult_open")
    ec = api.get("clinician_pcp", f"/api/cases/{econ}").json()["econsults"][0]
    assert (ec["from_person"]["name"], ec["from_person"]["role"]) == ("Dr Sara", "family medicine") and ec["to_person"]["name"] == "Dr Omar"
    ref = scenario_id(app, "rejected_referral")
    r = api.get("clinician_pcp", f"/api/cases/{ref}").json()["referral"]
    assert r["to_person"]["name"] == "Dr Omar" and r["from_person"]["name"] == "Dr Sara"


# ---------------------------------------------------------------- 15. simulation alignment


def test_simulation_uses_the_dashboards_bands_sex_codes_and_the_engine_thresholds():
    from app.api import dashboard
    from app.engine import demographics
    from app.sim import cohort

    assert dashboard.AGE_BANDS is demographics.AGE_BANDS and cohort.AGE_BANDS == demographics.AGE_BAND_LABELS
    rows = cohort.generate_region("AUH", 400, 7) + cohort.generate_region("YDE", 400, 7)
    assert {r["age_band"] for r in rows} <= set(demographics.AGE_BAND_LABELS) and {r["sex"] for r in rows} == {"F", "M"}
    assert all(r["age_band"] == demographics.age_band(r["age"]) for r in rows)
    assert (cohort.SEVERE_SBP, cohort.SEVERE_DBP) == (engine.config.value("thresholds", "severe_systolic"), engine.config.value("thresholds", "severe_diastolic"))
    assert (cohort.RAISED_SBP, cohort.RAISED_DBP) == (engine.config.value("thresholds", "raised_systolic"), engine.config.value("thresholds", "raised_diastolic"))
    assert all(r["urgency"] == (engine.classify(r["screening_sbp"], r["screening_dbp"]) or "NOT_ACTIONABLE") for r in rows)
    assert {r["nationality_group"] for r in rows if r["region"] == "YDE"} == {"Cameroonian"}


def test_the_engine_does_not_import_the_simulation_or_the_wording():
    for path in (APP_DIR / "engine").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "app.sim" not in src and "app.wording" not in src and "app.api" not in src and "app.db" not in src, path.name


def test_checked_in_data_files_use_the_shared_codes():
    data = APP_DIR.parent / "data"
    header, first = (data / "cohort_auh.csv").read_text(encoding="utf-8").splitlines()[:2]
    assert "age_band" in header and re.search(r",(18-34|35-49|50-64|65\+),(F|M),", first)
    assert "`18-34`, `35-49`, `50-64`, `65+`" in (data / "DATA_CARD.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- templates added in this pass follow the content rules

NEW_TEMPLATES = ["teach_back_question_app", "reminder_home_readings", "reminder_home_readings_sms", "reminder_booking",
                 "reminder_booking_sms", "appointment_reminder_sms", "red_flag_check", "red_flag_check_sms", "urgent_red_flags_sms"] + [
    f"plan_action_{k}_{s}" for k in ("salt", "activity", "sleep", "home_bp_check") for s in ("full", "smaller", "smallest")]


@pytest.mark.parametrize("tid", NEW_TEMPLATES)
@pytest.mark.parametrize("lang", ["en", "ar", "fr"])
def test_new_templates_render_plainly_in_every_language(tid, lang):
    from app.wording import render
    from app.wording.core import get_template
    from app.wording.validator import find_blocked

    tpl = get_template(tid)
    out = render(tid, lang, tpl["sample_slots"][lang]).text
    assert out.strip() and "{" not in out
    assert find_blocked(out, lang) == []  # no diagnosis or alarm words
    assert "—" not in out and "→" not in out and "->" not in out  # no em-dashes or arrows
    assert not re.search("[٠-٩]", out)  # Latin digits for clinical values
    limits = tpl["channel_limits"]
    if tid.endswith("_sms"):
        assert len(out) <= limits["sms"][lang]
        assert tpl["sms_chars_with_sample_slots"][lang] == len(out)


# ---------------------------------------------------------------- SMS reply grammar (SPEC section 6)


def last(thread: list[dict]) -> dict:
    return thread[-1]


def test_whole_yaounde_flow_by_replies(api, app):
    cid = api.case_id("patient_yde")
    out = [m["template_id"] for m in api.get("patient_yde", "/api/my/messages").json() if m["direction"] == "OUT"]
    assert out == ["result_raised"]  # an SMS thread starts with the result only
    t = reply(api, "patient_yde", "1")
    assert last(t)["template_id"] == "red_flag_check"
    t = reply(api, "patient_yde", "2")
    assert last(t)["template_id"] == "teach_back_question" and all(x in last(t)["text"] for x in ("A)", "B)", "C)"))
    t = reply(api, "patient_yde", "A")  # wrong
    assert [m["template_id"] for m in t[-2:]] == ["teach_back_simpler", "teach_back_question"]
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == "NOTIFIED" and not open_tasks(app, cid, "TEACH_BACK_CALL")
    t = reply(api, "patient_yde", "c)")  # second wrong answer: the coordinator call task
    assert len(open_tasks(app, cid, "TEACH_BACK_CALL")) == 1 and last(t)["template_id"] == "teach_back_question"
    t = reply(api, "patient_yde", " b. ")  # right, any case, trailing dot
    assert last(t)["template_id"] == "confirmation_hbpm_instructions" and "150/95" in last(t)["text"] and len(last(t)["text"]) <= 160
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["state"] == "ACKNOWLEDGED" and d["urgent"] is False
    with app.state.db.session() as s:
        assert s.get(Case, cid).patient_confidence is None  # not asked on SMS, no invented value
        assert s.get(Case, cid).sms_prompt is None
    passed = events_of(app, cid, "TEACH_BACK_PASSED")
    assert passed and passed[0].payload["confidence"] is None
    t = reply(api, "patient_yde", "150/95")
    assert last(t)["template_id"] == "reply_received"
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["readings"][-1]["systolic"] == 150


def test_a_digit_while_teach_back_is_open_is_not_an_answer(api, app):
    cid = api.case_id("patient_yde")
    reply(api, "patient_yde", "1")
    reply(api, "patient_yde", "2")
    for digit in ("1", "2", "3"):
        t = reply(api, "patient_yde", digit)
        assert [m["template_id"] for m in t[-2:]] == ["reply_not_understood", "teach_back_question"]  # asked again, nothing scored
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == "NOTIFIED"
    with app.state.db.session() as s:
        assert s.get(Case, cid).teach_back_failures == 0
    assert [e.type for e in events_of(app, cid)].count("TEACH_BACK_FAILED") == 0


def test_a_letter_is_not_a_red_flag_answer_and_french_words_are(api):
    cid = api.case_id("patient_yde")
    reply(api, "patient_yde", "1")
    t = reply(api, "patient_yde", "B")
    assert [m["template_id"] for m in t[-2:]] == ["reply_not_understood", "red_flag_check"]
    t = reply(api, "patient_yde", "Non")
    assert last(t)["template_id"] == "teach_back_question"
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["urgent"] is False


def test_french_oui_is_a_yes(api):
    cid = api.case_id("patient_yde")
    reply(api, "patient_yde", "1")
    t = reply(api, "patient_yde", "OUI")
    assert any(m["template_id"] == "urgent_red_flags_sms" for m in t)
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["urgent"] is True


def test_the_result_stage_accepts_only_1(api):
    cid = api.case_id("patient_yde")
    for bad in ("2", "A", "OUI", "150/95"):
        assert last(reply(api, "patient_yde", bad))["template_id"] == "reply_not_understood"
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == "NOTIFIED"


@pytest.mark.parametrize("steps", [[], ["1"], ["1", "2"], ["1", "2", "B"], ["1", "2", "B", "150/95"]])
def test_zero_means_call_me_in_every_state(api, app, steps):
    cid = api.case_id("patient_yde")
    for step in steps:
        reply(api, "patient_yde", step)
    state_before = api.get("nurse_yde", f"/api/cases/{cid}").json()["state"]
    t = reply(api, "patient_yde", "0")
    assert last(t)["template_id"] == "call_requested"
    assert len(open_tasks(app, cid, "COORDINATOR_CALL")) == 1
    reply(api, "patient_yde", "0")
    assert len(open_tasks(app, cid, "COORDINATOR_CALL")) == 1  # once
    assert api.get("nurse_yde", f"/api/cases/{cid}").json()["state"] == state_before  # it answered nothing


def test_two_no_longer_means_call_me(api, app):
    cid = api.case_id("patient_yde")
    reply(api, "patient_yde", "2")
    assert not open_tasks(app, cid, "COORDINATOR_CALL")


def test_check_in_letters_work_in_care_and_a_digit_does_not(api):
    drive_khalid(api, "IN_CARE")
    reply(api, "patient_auh", "C")  # an app patient may use the thread too
    assert api.my_case("patient_auh")["plan"][1]["size"] == "smaller"
    assert last(reply(api, "patient_auh", "2"))["template_id"] == "reply_not_understood"


def test_stop_and_severe_reading_still_behave_inside_the_grammar(api, app):
    cid = api.case_id("patient_yde")
    ack_by_sms(api)
    t = reply(api, "patient_yde", "185/115")
    assert last(t)["template_id"] == "result_severe" and "urgences" in last(t)["text"]
    t = reply(api, "patient_yde", "STOP")
    assert last(t)["template_id"] == "stop_confirmed"
    n = len(messages_out(app, cid))
    reply(api, "patient_yde", "0")  # call me still works after STOP, and no SMS goes out
    assert len(messages_out(app, cid)) == n and open_tasks(app, cid, "COORDINATOR_CALL")


def test_latest_outbound_message_lists_the_valid_replies(api):
    def valid(thread):
        out = [m for m in thread if m["direction"] == "OUT"]
        assert all(not m["valid_replies"] for m in out[:-1])
        return [(v["reply"], v["meaning_key"]) for v in out[-1]["valid_replies"]]

    assert valid(api.get("patient_yde", "/api/my/messages").json()) == [("1", "reply.read"), ("0", "reply.call_me")]
    assert valid(reply(api, "patient_yde", "1")) == [("1", "reply.yes"), ("2", "reply.no"), ("0", "reply.call_me")]
    assert valid(reply(api, "patient_yde", "2")) == [("A", "reply.option_a"), ("B", "reply.option_b"), ("C", "reply.option_c"),
                                                     ("0", "reply.call_me")]
    assert valid(reply(api, "patient_yde", "B")) == [("SYS/DIA", "reply.reading"), ("0", "reply.call_me")]


def test_every_sms_template_states_its_replies_and_nothing_says_two_for_a_call():
    from app.wording import render
    from app.wording.core import LANGUAGES, TEMPLATE_DIR, get_template

    for path in sorted(TEMPLATE_DIR.glob("*_sms.yaml")):
        tpl = get_template(path.stem)
        for lang in LANGUAGES:
            assert not re.search(r"(Reply|Répondez|أرسل)\s+2\s+(for a call|pour un appel|لمكالمة)", tpl["text"][lang]), (path.stem, lang)
    for tid in ("reminder_ack_sms", "reminder_booking_sms", "reminder_home_readings_sms", "no_blame_checkin_sms",
                "appointment_booked_sms", "result_raised_sms"):
        for lang in LANGUAGES:
            assert "0" in get_template(tid)["text"][lang], (tid, lang)
    for lang in LANGUAGES:  # the questions state their own valid replies
        tb = render("teach_back_question_sms", lang, {"reading": "152/96"}).text
        assert "A" in tb and "B" in tb and "C" in tb and "1." not in tb
        rf = render("red_flag_check_sms", lang, {}).text
        assert "1" in rf and "2" in rf and "0" in rf


def test_fhir_displays_have_no_role_suffix(api, app):
    cid = scenario_id(app, "rejected_referral")
    body = api.get("clinician_pcp", f"/api/cases/{cid}/fhir").text
    for suffix in ("(hypertension clinic)", "(family medicine)", "(care coordinator)"):
        assert suffix not in body
    assert "Dr Omar" in body
    k = drive_khalid(api, "IN_CARE")
    bundle = api.get("clinician_pcp", f"/api/cases/{k}/fhir").text
    assert "(care coordinator)" not in bundle and "(hypertension clinic)" not in bundle


# ---------------------------------------------------------------- phone-thread safety: staff see a severe reading


def test_severe_phone_reading_reaches_the_right_staff_and_only_them(api, app):
    cid = api.case_id("patient_yde")
    ack_by_sms(api)
    reply(api, "patient_yde", "185/115")
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["urgent"] is True and d["severity"] == "SEVERE"
    assert api.get("nurse_yde", "/api/cases?queue=urgent").json()["cases"][0]["id"] == cid
    tasks = open_tasks(app, cid, "URGENT_REVIEW")
    assert len(tasks) == 1 and tasks[0].owner_role == "clinician" and tasks[0].due_at
    with app.state.db.session() as s:
        owner = s.get(User, tasks[0].owner_user_id)
        assert owner.persona_key == "clinician_yde" and owner.region == "YDE"
    # the Yaounde clinician sees the case in the urgent queue and the task in the detail
    row = api.get("clinician_yde", "/api/cases?queue=urgent").json()["cases"][0]
    assert row["id"] == cid and row["flags"]["urgent_review_pending"] and row["reason_code"] == "URGENT_SEVERE"
    detail = api.get("clinician_yde", f"/api/cases/{cid}").json()
    review = [t for t in detail["tasks"] if t["type"] == "URGENT_REVIEW" and t["status"] == "OPEN"]
    assert len(review) == 1 and detail["urgent_review_due_at"] == review[0]["due_at"]
    # an Abu Dhabi clinician and coordinator do not see it
    assert cid not in [c["id"] for c in api.get("clinician_pcp", "/api/cases").json()["cases"]]
    assert api.get("clinician_pcp", f"/api/cases/{cid}").status_code == 403
    assert cid not in [c["id"] for c in api.get("coordinator_auh", "/api/cases").json()["cases"]]


def test_yaounde_clinician_personas_are_returned_with_listed_flag(api):
    personas = {p["persona"]: p for p in api.client.get("/api/personas").json()}
    assert personas["clinician_yde"]["listed"] is True
    assert personas["specialist_yde"]["listed"] is False and personas["specialist_yde"]["region"] == "YDE"
    assert all(personas[k]["listed"] for k in ("patient_auh", "coordinator_auh", "clinician_pcp", "clinician_specialist", "patient_yde",
                                                "nurse_yde", "analyst"))
    for key in ("clinician_yde", "specialist_yde"):
        p = personas[key]
        assert set(p["display_names"]) == {"en", "ar", "fr"} == set(p["role_titles"]) and all(p["display_names"].values())
    assert personas["clinician_yde"]["display_names"]["ar"] == "د. بريس"


def test_urgent_review_due_at_is_on_the_case_detail(api, app):
    severe = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "DUE-1", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                                "readings": [{"systolic": 185, "diastolic": 115}]}).json()["case_id"]
    d = api.get("clinician_pcp", f"/api/cases/{severe}").json()
    due, opened = datetime.fromisoformat(d["urgent_review_due_at"]), datetime.fromisoformat(d["opened_at"])
    assert timedelta(hours=3.9) < due - opened < timedelta(hours=4.1)  # 4 hours, not the 72 hours of next_step
    assert d["next_step"]["due_at"] != d["urgent_review_due_at"]
    assert api.act("clinician_pcp", severe, "complete_urgent_review", {"note": "Phoned the patient"}).status_code == 200
    assert api.get("clinician_pcp", f"/api/cases/{severe}").json()["urgent_review_due_at"] is None
    assert api.get("clinician_pcp", f"/api/cases/{scenario_id(app, 'unowned')}").json()["urgent_review_due_at"] is None


def test_short_note_is_a_localised_domain_error(api):
    severe = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "NOTE-1", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                                "readings": [{"systolic": 185, "diastolic": 115}]}).json()["case_id"]
    h = api.as_("clinician_pcp")
    url = f"/api/cases/{severe}/actions"
    en = api.client.post(url, headers=h, json={"action": "complete_urgent_review", "payload": {"note": ""}})
    assert en.status_code == 422 and en.json() == {"code": "NOTE_TOO_SHORT", "message": "A note of at least 3 characters is needed."}
    for lang, probe in (("ar", "يلزم"), ("fr", "Une note")):
        r = api.client.post(url, headers={**h, "Accept-Language": lang}, json={"action": "complete_urgent_review", "payload": {"note": "ab"}})
        assert r.json()["code"] == "NOTE_TOO_SHORT" and probe in r.json()["message"] and "String should" not in r.json()["message"]
    other = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "NOTE-2", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                               "readings": [{"systolic": 150, "diastolic": 95}]}).json()["case_id"]
    r = api.client.post(f"/api/cases/{other}/actions", headers=api.as_("coordinator_auh"), json={"action": "escalate", "payload": {"reason": "x"}})
    assert r.status_code == 422 and r.json()["code"] == "NOTE_TOO_SHORT"
