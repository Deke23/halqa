import re
from unittest import mock

import httpx
import pytest
import yaml

from app.wording import MissingSlotError, UnknownTemplateError, list_templates, render, reword, validate
from app.wording.core import LANGUAGES, TEMPLATE_DIR, get_template
from app.wording.validator import blocked_words, find_blocked

SPEC_IDS = ["result_raised", "result_severe", "teach_back_question", "teach_back_simpler", "reminder_ack",
            "confirmation_hbpm_instructions", "confirmation_abpm_booking", "referral_sent", "referral_accepted",
            "appointment_booked", "appointment_reminder", "weekly_action", "no_blame_checkin", "plan_smaller",
            "case_closed_summary", "urgent_red_flags"]
SMS_IDS = ["result_raised_sms", "result_severe_sms", "teach_back_question_sms", "reminder_ack_sms",
           "confirmation_hbpm_instructions_sms", "referral_accepted_sms", "appointment_booked_sms",
           "weekly_action_sms", "no_blame_checkin_sms"]
ALL_IDS = SPEC_IDS + SMS_IDS


def sample(tid, lang):
    return get_template(tid)["sample_slots"][lang]


def test_every_spec_id_exists_with_all_languages():
    ids = {t["id"] for t in list_templates()}
    assert set(ALL_IDS) <= ids
    for t in list_templates():
        assert t["languages"] == ["en", "ar", "fr"]
        assert t["version"] >= 1 and t["purpose"] and t["channel_limits"] is not None


@pytest.mark.parametrize("tid", ALL_IDS)
@pytest.mark.parametrize("lang", LANGUAGES)
def test_renders_with_required_slots(tid, lang):
    r = render(tid, lang, sample(tid, lang))
    assert r.text.strip() and "{" not in r.text and "}" not in r.text
    assert r.template_id == tid and r.language == lang and r.template_version >= 1


@pytest.mark.parametrize("tid", ALL_IDS)
def test_all_placeholders_are_declared_slots(tid):
    tpl = get_template(tid)
    for lang in LANGUAGES:
        used = set(re.findall(r"\{(\w+)\}", tpl["text"][lang]))
        assert used == set(tpl["required_slots"]), (tid, lang)


def test_missing_slot_raises_clear_error():
    with pytest.raises(MissingSlotError, match="reading"):
        render("result_raised", "en", {"name": "A", "due_date": "x"})
    with pytest.raises(UnknownTemplateError):
        render("nope", "en", {})


def test_render_is_deterministic():
    s = sample("result_raised", "fr")
    assert render("result_raised", "fr", s) == render("result_raised", "fr", s)


@pytest.mark.parametrize("tid", SMS_IDS)
def test_sms_length_limits_and_declared_counts(tid):
    tpl = get_template(tid)
    for lang in LANGUAGES:
        n = len(render(tid, lang, sample(tid, lang)).text)
        assert n <= tpl["channel_limits"]["sms"][lang], (tid, lang, n)
        assert tpl["sms_chars_with_sample_slots"][lang] == n, f"YAML char count is stale for {tid} {lang}"


def test_french_sms_within_160():
    for tid in SMS_IDS:
        assert len(render(tid, "fr", sample(tid, "fr")).text) <= 160


@pytest.mark.parametrize("tid", ALL_IDS)
@pytest.mark.parametrize("lang", LANGUAGES)
def test_our_templates_do_not_use_blocked_words(tid, lang):
    text = render(tid, lang, sample(tid, lang)).text
    assert find_blocked(text, lang) == []


def test_blocked_lists_cover_all_languages():
    for lang in LANGUAGES:
        assert len(blocked_words()[lang]) >= 8


@pytest.mark.parametrize("tid", ALL_IDS)
def test_no_hard_coded_phone_numbers_or_streak_language(tid):
    tpl = get_template(tid)
    for lang in LANGUAGES:
        raw = tpl["text"][lang]
        assert not re.search(r"\d{7,}", raw), "no phone numbers in template text"
        assert not re.search(r"\b(streak|lose|lost|perdu|perdre)\b|سلسلة", raw, re.I)


def test_urgent_template_takes_emergency_instruction_slot():
    assert "emergency_instruction" in get_template("urgent_red_flags")["required_slots"]
    assert "emergency_instruction" in get_template("result_severe")["required_slots"]


def test_no_blame_checkin_says_missed_week_is_normal_and_smaller():
    t = get_template("no_blame_checkin")["text"]
    assert "normal" in t["en"] and "smaller" in t["en"]
    assert "طبيعي" in t["ar"] and "أصغر" in t["ar"]
    assert "normale" in t["fr"] and "petite" in t["fr"]


def test_teach_back_structure():
    for tid in ("teach_back_question", "teach_back_question_sms"):
        tpl = get_template(tid)
        assert tpl["correct"] in (1, 2, 3)
        for lang in LANGUAGES:
            assert len(tpl["options"][lang]) == 3
    r = render("teach_back_question", "fr", {"reading": "164/102"})
    assert r.extra["correct"] == 2 and "2. " in r.text


def test_arabic_templates_are_arabic_with_latin_clinical_values():
    for tid in SPEC_IDS:
        text = render(tid, "ar", sample(tid, "ar")).text
        assert not re.search(r"[٠-٩]", text), "clinical values stay in Latin digits"
        assert validate(text, text, "ar", sample(tid, "ar"))["passed"] is True


def test_templates_yaml_ids_match_filenames():
    for path in TEMPLATE_DIR.glob("*.yaml"):
        assert yaml.safe_load(path.read_text(encoding="utf-8"))["id"] == path.stem


# ---------------------------------------------------------------- validator

SLOTS = {"name": "Khalid", "reading": "152/96", "due_date": "Friday 22 November"}
ORIG = render("result_raised", "en", SLOTS).text


def ok(candidate, lang="en", original=ORIG, slots=SLOTS, max_length=None):
    return validate(original, candidate, lang, slots, max_length)


def test_good_rewording_accepted():
    cand = ("Hi Khalid. Your screening blood pressure was 152/96. This is a raised reading that needs checking. "
            "It does not mean you are ill and it is not a final result, as one reading can change from day to day. "
            "It is not an emergency, but please act before Friday 22 November. Next, check your blood pressure again, "
            "at home or at a clinic. We will show you how.")
    res = ok(cand)
    assert res["passed"] and res["failed_reason"] is None and len(res["checks"]) == 6


def test_changed_number_rejected():
    res = ok(ORIG.replace("152/96", "125/96"))
    assert not res["passed"] and "slots_preserved" in res["failed_reason"]


def test_added_number_rejected():
    res = ok(ORIG + " Call 0555 now or check in 3 hours.")
    assert not res["passed"] and "no_new_numbers" in res["failed_reason"]


def test_name_and_date_must_survive():
    assert not ok(ORIG.replace("Khalid", "Mr K"))["passed"]
    assert not ok(ORIG.replace("Friday 22 November", "next week"))["passed"]


def test_diagnosis_word_rejected():
    res = ok(ORIG.replace("raised reading", "hypertension"))
    assert not res["passed"] and "no_blocked_words" in res["failed_reason"]
    assert not ok(ORIG + " This is dangerous.")["passed"]


def test_blocked_words_in_arabic_and_french():
    ar = render("result_raised", "ar", sample("result_raised", "ar")).text
    assert not validate(ar, ar + " تم تشخيص", "ar", sample("result_raised", "ar"))["passed"]
    fr = render("result_raised", "fr", sample("result_raised", "fr")).text
    assert not validate(fr, fr + " Vous êtes hypertendu.", "fr", sample("result_raised", "fr"))["passed"]


def test_wrong_script_rejected():
    ar_slots = sample("result_raised", "ar")
    ar = render("result_raised", "ar", ar_slots).text
    res = validate(ar, ORIG, "ar", ar_slots)  # English text claimed as Arabic
    assert not res["passed"]
    res = validate(ORIG, ar, "en", SLOTS)
    assert not res["passed"] and "script_matches_language" in res["failed_reason"]


def test_french_passed_as_english_rejected():
    fr_slots = sample("result_raised", "fr")
    fr = render("result_raised", "fr", fr_slots).text
    res = validate(ORIG, fr, "en", {})
    assert any(c["name"] == "script_matches_language" and not c["passed"] for c in res["checks"])


def test_too_long_rejected():
    assert not ok(ORIG + " " + "More words. " * 80)["passed"]
    assert not ok(ORIG, max_length=50)["passed"]


def test_empty_rejected():
    assert not ok("")["passed"] and not ok("   ")["passed"]


def test_arabic_indic_digits_count_as_changed():
    ar_slots = sample("result_raised", "ar")
    ar = render("result_raised", "ar", ar_slots).text
    assert not validate(ar, ar.replace("152/96", "١٥٢/٩٦"), "ar", ar_slots)["passed"]


# ---------------------------------------------------------------- reword and providers

def test_default_provider_makes_no_network_call(monkeypatch):
    monkeypatch.delenv("WORDING_PROVIDER", raising=False)
    with mock.patch.object(httpx, "post", side_effect=AssertionError("network used")) as post:
        r = reword(ORIG, "en", "warm", SLOTS)
    assert r.source == "TEMPLATE" and r.text == ORIG and not post.called


def _anthropic_env(monkeypatch):
    monkeypatch.setenv("WORDING_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def _resp(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request("POST", "http://x"))


def test_anthropic_good_result_accepted(monkeypatch):
    _anthropic_env(monkeypatch)
    cand = ORIG.replace("Hello", "Hi")
    with mock.patch.object(httpx, "post", return_value=_resp({"content": [{"type": "text", "text": cand}]})) as post:
        r = reword(ORIG, "en", "warm", SLOTS)
    assert r.source == "AI_REWORDED" and r.text == cand and r.validation["passed"]
    kwargs = post.call_args.kwargs
    assert kwargs["timeout"] == 10.0 and kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert kwargs["json"]["model"] == "claude-haiku-5-5"
    assert "without adding" in kwargs["json"]["system"] or "Do not add facts" in kwargs["json"]["system"]


def test_azure_good_result_accepted(monkeypatch):
    monkeypatch.setenv("WORDING_PROVIDER", "azure_openai")
    for k, v in dict(AZURE_OPENAI_ENDPOINT="https://example.openai.azure.com", AZURE_OPENAI_DEPLOYMENT="d",
                     AZURE_OPENAI_API_KEY="k", AZURE_OPENAI_API_VERSION="2024-06-01").items():
        monkeypatch.setenv(k, v)
    cand = ORIG.replace("Hello", "Hi")
    with mock.patch.object(httpx, "post", return_value=_resp({"choices": [{"message": {"content": cand}}]})) as post:
        r = reword(ORIG, "en", None, SLOTS)
    assert r.source == "AI_REWORDED"
    assert "/openai/deployments/d/chat/completions" in post.call_args.args[0]
    assert post.call_args.kwargs["timeout"] == 10.0


def test_bad_provider_output_falls_back_to_template(monkeypatch):
    _anthropic_env(monkeypatch)
    bad = ORIG.replace("152/96", "160/100")
    with mock.patch.object(httpx, "post", return_value=_resp({"content": [{"type": "text", "text": bad}]})):
        r = reword(ORIG, "en", None, SLOTS)
    assert r.source == "TEMPLATE" and r.text == ORIG and not r.validation["passed"] and r.validation["failed_reason"]


@pytest.mark.parametrize("exc", [httpx.TimeoutException("slow"), httpx.ConnectError("down"), RuntimeError("boom")])
def test_provider_failure_falls_back_and_never_raises(monkeypatch, exc):
    _anthropic_env(monkeypatch)
    with mock.patch.object(httpx, "post", side_effect=exc):
        r = reword(ORIG, "en", None, SLOTS)
    assert r.source == "TEMPLATE" and r.text == ORIG and r.validation["failed_reason"].startswith("provider_error")


def test_http_error_and_malformed_json_fall_back(monkeypatch):
    _anthropic_env(monkeypatch)
    with mock.patch.object(httpx, "post", return_value=_resp({"error": "x"}, status=500)):
        assert reword(ORIG, "en", None, SLOTS).source == "TEMPLATE"
    with mock.patch.object(httpx, "post", return_value=_resp({"unexpected": 1})):
        assert reword(ORIG, "en", None, SLOTS).source == "TEMPLATE"


def test_missing_key_falls_back(monkeypatch):
    monkeypatch.setenv("WORDING_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert reword(ORIG, "en", None, SLOTS).source == "TEMPLATE"


def test_wording_does_not_import_engine_api_db():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "wording"
    for p in root.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        pattern = r"(?m)^\s*(from|import)\s+(app\.(engine|api|db)|\.\.(engine|api|db))"
        assert not re.search(pattern, src), p.name
