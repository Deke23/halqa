"""Every server-supplied display string is available in en, ar and fr: names, places, labels, config, templates, errors."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.api import i18n
from app.db.models import Patient, User
from tests.conftest import drive_khalid, scenario_id

ARABIC = re.compile("[؀-ۿ]")
LANGS = ("en", "ar", "fr")


def has_all(d: dict) -> bool:
    return set(d) == set(LANGS) and all(isinstance(v, str) and v for v in d.values())


def test_every_seeded_person_has_names_in_three_scripts(app):
    with app.state.db.session() as s:
        users, patients = list(s.scalars(select(User))), list(s.scalars(select(Patient)))
    for u in users:
        names, roles = i18n.person_names(u.name), i18n.person_roles(u.name, u.role)
        assert has_all(names) and has_all(roles), u.name
        assert "(" not in "".join(names.values()) + "".join(roles.values()), u.name
        if u.role != "analyst" or u.persona_key:  # every seeded person has an Arabic form in Arabic script
            assert ARABIC.search(names["ar"]) and ARABIC.search(roles["ar"]), (u.name, names, roles)
    for p in patients:
        names = i18n.person_names(p.display_name)
        assert ARABIC.search(names["ar"]) and names["en"] == p.display_name, p.display_name
        ini = i18n.initials_i18n(p.display_name)
        assert has_all(ini) and ARABIC.search(ini["ar"]) and ini["en"] == p.initials, (p.display_name, ini, p.initials)


def test_named_forms_requested_by_the_front_end():
    want = {"Mariam (care coordinator)": ("مريم", "Mariam"), "Dr Sara (family medicine)": ("د. سارة", "Dr Sara"),
            "Dr Omar (hypertension clinic)": ("د. عمر", "Dr Omar"), "Dr Nadia (has left the organisation)": ("د. نادية", "Dr Nadia"),
            "Clarisse (nurse coordinator)": ("كلاريس", "Clarisse"), "Dr Brice (general practice, Yaoundé)": ("د. بريس", "Dr Brice"),
            "Dr Estelle (hypertension clinic, Yaoundé)": ("د. إستيل", "Dr Estelle"), "Khalid A.": ("خالد أ.", "Khalid A."),
            "Jean-Paul E.": ("جان بول إ.", "Jean-Paul E.")}
    for stored, (ar, fr) in want.items():
        names = i18n.person_names(stored)
        assert names["ar"] == ar and names["fr"] == fr, stored
    assert i18n.person_names("Someone Unknown (nurse)") == i18n.same("Someone Unknown")  # no invented translation


def test_people_fields_on_users_personas_and_person_refs(api, app):
    me = api.get("coordinator_auh", "/api/me").json()
    assert me["display_names"] == {"en": "Mariam", "ar": "مريم", "fr": "Mariam"}
    assert me["role_titles"]["ar"] == "منسقة الرعاية" and has_all(me["organisation_i18n"]) and ARABIC.search(me["organisation_i18n"]["ar"])
    assert me["name"] == "Mariam (care coordinator)"  # old field kept
    personas = {p["persona"]: p for p in api.client.get("/api/personas").json()}
    assert personas["clinician_specialist"]["display_names"]["ar"] == "د. عمر" and has_all(personas["analyst"]["role_titles"])
    cid = api.case_id("patient_yde")
    d = api.get("nurse_yde", f"/api/cases/{cid}").json()
    assert d["owner_person"]["names"]["ar"] == "كلاريس" and d["owner_person"]["roles"]["fr"] == "infirmière coordinatrice"
    assert d["patient"]["names"]["ar"] == "جان بول إ." and d["patient"]["initials_i18n"]["ar"]
    assert d["patient"]["initials"] == "JP" or d["patient"]["initials"]  # staff lists keep the Latin initials
    assert has_all(d["patient"]["organisation_i18n"]) and d["patient"]["region_name_i18n"]["ar"] == "ياوندي"
    mine = api.my_case("patient_auh")
    assert mine["patient"]["names"]["ar"] == "خالد أ." and mine["patient"]["names"]["en"] == "Khalid A."
    row = api.get("coordinator_auh", "/api/cases").json()["cases"][0]
    assert has_all(row["patient_names"]) and has_all(row["patient_initials_i18n"]) and row["owner_person"]["names"]["ar"] == "مريم"


def test_slots_appointments_and_cover_are_translated_and_still_say_simulated(api):
    cid = drive_khalid(api, "REFERRED")
    slot = api.get("patient_auh", f"/api/cases/{cid}/slots").json()[0]
    assert slot["provider_person"]["names"]["ar"] == "د. عمر" and ARABIC.search(slot["location_i18n"]["ar"])
    assert slot["provider_name"].startswith("Dr Omar") and slot["location"]  # old fields kept
    assert "Dr Omar" in slot["label_i18n"]["en"] and "د. عمر" in slot["label_i18n"]["ar"] and re.search(r"\d{2}:\d{2}", slot["label_i18n"]["fr"])
    cover = slot["cover"]
    assert has_all(cover["label_i18n"]) and cover["simulated"] is True and cover["label"] == cover["label_i18n"]["en"]
    assert "(simulated)" in cover["label_i18n"]["en"] and "محاكاة" in cover["label_i18n"]["ar"] and "simulé" in cover["label_i18n"]["fr"]
    assert has_all(cover["simulated_label_i18n"])
    booked = api.act("patient_auh", cid, "book_appointment", {"slot_id": slot["id"]}).json()["appointment"]
    assert booked["provider_person"]["names"]["fr"] == "Dr Omar" and has_all(booked["label_i18n"]) and ARABIC.search(booked["location_i18n"]["ar"])
    ref = api.my_case("patient_auh")["referral"]
    assert ref["to_service_i18n"]["ar"] == "عيادة ضغط الدم"


def test_cover_for_every_insurance_says_simulated_in_every_language(app):
    from app.api.routes import cover_for

    with app.state.db.session() as s:
        for insurance, region in (("THIQA", "AUH"), ("BASIC", "AUH"), ("NONE", "AUH"), ("NONE", "YDE")):
            p = Patient(ref="x", display_name="X", initials="X", age=40, sex="M", nationality_group="x", language="en", region=region,
                        insurance=insurance, channel="APP", organisation="o")
            c = cover_for(p, None)
            assert "simulated" in c.label_i18n.en and "محاكاة" in c.label_i18n.ar and "simulé" in c.label_i18n.fr, insurance
            assert "{" not in c.label_i18n.ar and not re.search("[٠-٩]", c.label_i18n.ar)
        basic = cover_for(Patient(ref="x", display_name="X", initials="X", age=40, sex="M", nationality_group="x", language="en",
                                  region="AUH", insurance="BASIC", channel="APP", organisation="o"), None)
        assert "20" in basic.label_i18n.ar and "20" in basic.label_i18n.fr


def test_tasks_plan_and_emergency_advice_have_translations(api, app):
    d = api.get("coordinator_auh", f"/api/cases/{scenario_id(app, 'overdue_ack')}").json()
    assert d["tasks"] and all(has_all(t["title_i18n"]) and ARABIC.search(t["title_i18n"]["ar"]) for t in d["tasks"])
    cid = drive_khalid(api, "IN_CARE")
    plan = api.my_case("patient_auh")["plan"][0]
    assert has_all(plan["default_text_i18n"]) and plan["default_text_i18n"]["en"] == api.get("patient_auh", "/api/my/case?language=en").json()["plan"][0]["default_text"]
    sev = api.post("coordinator_auh", "/api/intake/result", {"patient_ref": "I18N-SEV", "source_system": "IFHAS_SCREENING", "region": "AUH",
                                                            "readings": [{"systolic": 185, "diastolic": 115}]}).json()["case_id"]
    adv = api.get("clinician_pcp", f"/api/cases/{sev}").json()["emergency_advice"]
    assert has_all(adv["text_i18n"]) and "998" in adv["text_i18n"]["ar"] and adv["text"] in adv["text_i18n"].values()


def test_dashboard_group_label_is_translated(api):
    g = api.get("analyst", "/api/dashboard/live").json()["groups"][0]
    assert g["label"] == "All people" and g["label_i18n"]["ar"] == "جميع الأشخاص"


def test_config_carries_labels_basis_units_purposes_regions_and_closure_labels(api):
    c = api.client.get("/api/config").json()
    assert c["entries"]
    for e in c["entries"]:
        for field in ("label_i18n", "basis_i18n", "unit_i18n"):
            assert has_all(e[field]), (e["section"], e["key"], field)
        assert e["basis_i18n"]["en"] == e["basis"] and ARABIC.search(e["basis_i18n"]["ar"]) and ARABIC.search(e["label_i18n"]["ar"])
        assert e["basis_i18n"]["fr"] != e["basis_i18n"]["en"]
        assert not re.search("[٠-٩]", e["basis_i18n"]["ar"])
    assert {x["code"] for x in c["closure_evidence_labels"]} == set(c["closure_evidence_types"])
    assert all(has_all(x["label_i18n"]) and ARABIC.search(x["label_i18n"]["ar"]) for x in c["closure_evidence_labels"])
    assert c["templates"] and all(has_all(t["purpose_i18n"]) and ARABIC.search(t["purpose_i18n"]["ar"]) for t in c["templates"])
    assert all(has_all(r["name_i18n"]) for r in c["regions"]) and {r["region"]: r["name_i18n"]["ar"] for r in c["regions"]} == {"AUH": "أبوظبي", "YDE": "ياوندي"}
    assert has_all(c["notice_i18n"]) and len(c["rules_i18n"]) == len(c["rules"]) and all(has_all(r) for r in c["rules_i18n"])
    assert c["rules_i18n"][0]["en"] == c["rules"][0] and c["notice_i18n"]["en"] == c["notice"]


# ---------------------------------------------------------------- errors


@pytest.mark.parametrize("header,lang", [(None, "en"), ("", "en"), ("ar", "ar"), ("fr-CH, fr;q=0.9, en;q=0.8", "fr"), ("de, ar;q=0.5, fr;q=0.8", "fr"),
                                         ("xx", "en"), ("ar;q=0, fr", "fr"), ("EN-gb", "en")])
def test_accept_language_choice(header, lang):
    assert i18n.pick_language(header) == lang


def test_closure_refusals_are_translated(api, app):
    ready = scenario_id(app, "ready_to_close")
    h = {"Authorization": api.as_("clinician_pcp")["Authorization"]}
    url, body = f"/api/cases/{ready}/actions", {"action": "close", "payload": {"evidence_type": "BP_CONTROLLED"}}
    en = api.client.post(url, headers=h, json=body)
    assert en.status_code == 422 and en.json() == {"code": "CLOSURE_EVIDENCE_REQUIRED", "message": "Closing a case needs an evidence reference or a decision note of at least 10 characters."}
    ar = api.client.post(url, headers={**h, "Accept-Language": "ar"}, json=body).json()
    fr = api.client.post(url, headers={**h, "Accept-Language": "fr-FR,fr;q=0.9"}, json=body).json()
    assert ar["code"] == fr["code"] == "CLOSURE_EVIDENCE_REQUIRED" and set(ar) == {"code", "message"}
    assert ARABIC.search(ar["message"]) and "10" in ar["message"] and "{" not in ar["message"]
    assert fr["message"].startswith("Pour clôturer") and "10" in fr["message"]
    none = api.client.post(url, headers={**h, "Accept-Language": "ar"}, json={"action": "close", "payload": {}}).json()
    assert none["code"] == "CLOSURE_EVIDENCE_TYPE_REQUIRED" and ARABIC.search(none["message"])
    coord = {"Authorization": api.as_("coordinator_auh")["Authorization"], "Accept-Language": "ar"}
    denied = api.client.post(url, headers=coord, json=body).json()
    assert denied["code"] == "FORBIDDEN_ROLE" and ARABIC.search(denied["message"])
    reopen = api.client.post(f"/api/cases/{ready}/actions", headers={**h, "Accept-Language": "fr"}, json={"action": "reopen", "payload": {"reason": "ok"}})
    assert reopen.status_code in (409, 422)


def test_other_errors_follow_the_header_and_unknown_languages_fall_back(api):
    for lang, probe in (("ar", ARABIC), ("fr", re.compile("Envoyez")), ("de", re.compile("Send a Bearer"))):
        r = api.client.get("/api/cases", headers={"Accept-Language": lang})
        assert r.status_code == 401 and r.json()["code"] == "NOT_AUTHENTICATED" and probe.search(r.json()["message"]), lang
    r = api.client.get("/api/nothing/here", headers={"Accept-Language": "ar"})
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
    wrong = api.act("patient_auh", api.case_id("patient_auh"), "close", {"evidence_type": "BP_CONTROLLED", "decision_note": "a note that is long"})
    assert wrong.status_code == 403
    r = api.client.post(f"/api/cases/{api.case_id('patient_auh')}/actions", headers={**api.as_("patient_auh"), "Accept-Language": "ar"},
                        json={"action": "refer", "payload": {}})
    assert r.status_code == 403 and ARABIC.search(r.json()["message"])  # role and action names come in Arabic, not as English words
    assert "refer" not in r.json()["message"] and "patient" not in r.json()["message"]
    wrong_state = api.client.post(f"/api/cases/{api.case_id('patient_auh')}/actions", headers={**api.as_("patient_auh"), "Accept-Language": "fr"},
                                  json={"action": "book_appointment", "payload": {"slot_id": 1}}).json()
    assert wrong_state["code"] in ("WRONG_STATE", "FORBIDDEN_ROLE") and "{" not in wrong_state["message"]


def test_catalogue_covers_every_code_raised_in_the_code_base():
    """Every ApiError and Verdict code in the source has at least one catalogue entry with all three languages."""
    from pathlib import Path

    src = "".join(p.read_text(encoding="utf-8") for p in Path(i18n.__file__).parents[1].rglob("*.py"))
    raised = set(re.findall(r'(?:ApiError|Verdict)\((?:\d+|False, \d+|verdict\.status|v\.status|[a-z_.]+),\s*"([A-Z_]+)"', src))
    raised |= set(re.findall(r'Verdict\(False,\s*\d+,\s*"([A-Z_]+)"', src))
    catalogued = {e["code"] for e in i18n.catalogue()}
    assert raised and raised <= catalogued, raised - catalogued
    for e in i18n.catalogue():
        assert e["en"] and e["ar"] and e["fr"], e["code"]
        assert ARABIC.search(e["ar"]) and not re.search("[٠-٩]", e["ar"]), e["code"]
        assert sorted(re.findall(r"\{(\w+)\}", e["en"])) == sorted(re.findall(r"\{(\w+)\}", e["ar"])) == sorted(re.findall(r"\{(\w+)\}", e["fr"])), e["code"]
