import json
import re

import pytest

from app.sim import cohort, demo_series, pathway, run

MEASURES = ["time_to_notification_h", "time_to_acknowledgement_h", "time_to_confirmation_d", "time_to_consultation_d",
            "time_to_care_d", "referral_completion_rate", "appointment_completion_rate", "treatment_initiation_rate",
            "unresolved_results", "teach_back_pass_rate", "patient_confidence_mean", "plan_checkin_rate",
            "re_engagement_after_lapse_rate"]


@pytest.fixture(scope="module")
def doc():
    return run.build(seed=7, size=1500, write_dir=None)


def test_cohort_deterministic_and_documented():
    a = cohort.generate_region("AUH", 300, 1)
    assert a == cohort.generate_region("AUH", 300, 1)
    assert a != cohort.generate_region("AUH", 300, 2)
    assert set(a[0]) == set(cohort.FIELDS)
    assert {r["urgency"] for r in a} <= {"SEVERE", "RAISED", "NOT_ACTIONABLE"}
    assert all(r["actionable"] == (r["urgency"] != "NOT_ACTIONABLE") for r in a)


def test_cohort_values_plausible_and_region_specific():
    auh = cohort.generate_region("AUH", 2000, 3)
    yde = cohort.generate_region("YDE", 2000, 3)
    assert {r["nationality_group"] for r in auh} == {"Emirati", "Expatriate Arab", "South Asian", "Other"}
    assert len({r["nationality_group"] for r in yde}) == 1
    assert {r["preferred_language"] for r in yde} <= {"fr", "en"}
    assert all(18 <= r["age"] <= 85 for r in auh + yde)
    assert 0.05 < cohort.summary(auh)["actionable_share"] < 0.4


def test_simulation_deterministic_same_seed_identical_json():
    a = json.dumps(run.build(seed=11, size=800, write_dir=None), sort_keys=True)
    b = json.dumps(run.build(seed=11, size=800, write_dir=None), sort_keys=True)
    c = json.dumps(run.build(seed=12, size=800, write_dir=None), sort_keys=True)
    assert a == b and a != c


def test_written_files_are_deterministic_lf(tmp_path):
    run.build(seed=5, size=600, write_dir=tmp_path / "a")
    run.build(seed=5, size=600, write_dir=tmp_path / "b")
    for name in ("simulation_results.json", "demo_series.json", "DATA_CARD.md", "cohort_auh.csv", "cohort_yde.csv"):
        x, y = (tmp_path / "a" / name).read_bytes(), (tmp_path / "b" / name).read_bytes()
        assert x == y and b"\r" not in x


def test_parameter_table_complete_and_only_allowed_published():
    params = pathway.load_params()
    allowed = set(params["published_sources"].values())
    assert len(allowed) == 4
    for name, p in params["parameters"].items():
        assert p["kind"] in ("published", "assumption"), name
        assert p["source"] and "value" in p and p["unit"] and p["rationale"], name
        if p["kind"] == "published":
            assert p["source"] in allowed, name
        else:
            assert p["source"] == "Assumption", name


def test_every_step_has_both_arms_parameters():
    names = set(pathway.load_params()["parameters"])
    for prefix in ("p_notified", "p_acknowledged", "p_confirmation_completed", "p_referral_sent", "p_referral_accepted",
                   "p_appointment_booked", "p_visit_attended", "p_care_recorded", "notify_delay_median_d"):
        assert f"baseline.{prefix}" in names and f"with_loop.{prefix}" in names


def test_json_has_metadata_parameters_results_sensitivity(doc):
    md = doc["metadata"]
    assert md["seed"] == 7 and md["cohort_size_per_region"] == 1500 and md["generated_at"]
    assert "not evidence of clinical effectiveness" in md["disclaimer"] and "simulated results on synthetic people" in md["disclaimer"]
    assert doc["parameters"] and set(doc["sensitivity"]) == {"AUH", "YDE"}
    for region in doc["sensitivity"]:
        s = doc["sensitivity"][region]
        assert len(s["top3"]) == 3
        for item in s["top3"]:
            assert {"low", "base", "high"} <= set(item)


def test_measures_present_for_every_region_arm_split_group(doc):
    for region in ("AUH", "YDE"):
        for arm in ("baseline", "with_loop"):
            splits = doc["results"][region][arm]
            assert set(splits) == {"none", "language", "nationality_group", "sex", "age_band"}
            for groups in splits.values():
                assert groups
                for m in groups.values():
                    for name in MEASURES:
                        assert name in m, name
                        assert "n" in m[name] and "suppressed" in m[name]
                    assert set(m["unresolved_results"]["delay_reasons"]) == set(pathway.REASON_LABELS)


def test_baseline_has_no_loop_only_measures(doc):
    m = doc["results"]["AUH"]["baseline"]["none"]["all"]
    for k in ("teach_back_pass_rate", "plan_checkin_rate", "patient_confidence_mean", "re_engagement_after_lapse_rate"):
        assert m[k]["n"] == 0 and m[k]["suppressed"] and m[k]["value"] is None


def test_small_cell_suppression_applied_everywhere(doc):
    seen_suppressed = False

    def walk(node):
        nonlocal seen_suppressed
        if isinstance(node, dict):
            if "suppressed" in node and "n" in node:
                assert node["suppressed"] == (node["n"] < 5), node
                if node["suppressed"]:
                    seen_suppressed = True
                    assert all(v is None for k, v in node.items() if k in ("value", "median", "p90", "numerator", "count", "rate"))
            for k, v in node.items():
                if k == "delay_reasons":
                    for r in v.values():
                        assert r["suppressed"] == (r["count"] is None)
                else:
                    walk(v)
    walk(doc["results"])
    assert seen_suppressed


def test_direct_suppression_helpers():
    assert pathway._rate(3, 4)["suppressed"] and pathway._rate(3, 4)["value"] is None
    assert not pathway._rate(3, 5)["suppressed"]
    import numpy as np
    assert pathway._time(np.array([1.0, 2.0, 3.0, 4.0]))["suppressed"]


def test_with_loop_is_better_but_not_implausibly_so(doc):
    for region in ("AUH", "YDE"):
        b = doc["results"][region]["baseline"]["none"]["all"]
        l = doc["results"][region]["with_loop"]["none"]["all"]
        assert l["care_reached_rate"]["value"] > b["care_reached_rate"]["value"]
        assert l["care_reached_rate"]["value"] < 0.5
        assert l["time_to_care_d"]["median"] < b["time_to_care_d"]["median"]


def test_demo_series_meet_spec():
    d = demo_series.build(3)
    assert set(d["personas"]) == {"patient_auh", "patient_yde"}
    for p in d["personas"].values():
        h = p["hbpm_week"]
        assert len(h["readings"]) == 28 and {r["day"] for r in h["readings"]} == set(range(1, 8))
        assert h["average_excluding_day_1"]["systolic"] >= 135 and h["average_excluding_day_1"]["diastolic"] >= 85
        a = p["abpm_day"]["daytime_average"]
        assert a["systolic"] >= 135 and a["diastolic"] >= 85
        assert len(p["wearable_diary"]["days"]) == 14
        assert not re.search(r"systolic|diastolic|bp", json.dumps(p["wearable_diary"]["days"]), re.I)
    assert d["personas"]["patient_auh"]["screening_reading"] == "152/96"
    assert d["personas"]["patient_yde"]["screening_reading"] == "164/102"
    assert d == demo_series.build(3)
