"""Regenerate every simulation output deterministically:  python -m app.sim.run

Writes to backend/data: cohort_auh.csv, cohort_yde.csv, DATA_CARD.md, simulation_results.json, demo_series.json.
Paths are resolved from this file's location, never from the current directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import cohort, datacard, demo_series, pathway

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_SEED = 20260101
FIXED_GENERATED_AT = "2026-01-01T00:00:00Z"  # fixed so output is byte-identical; pass --generated-at to override
COHORT_SIZE = 5000

DISCLAIMER = ("These are simulated results on synthetic people. They show what the system measures and are not "
              "evidence of clinical effectiveness. All probabilities other than the one published figure are assumptions "
              "listed in the parameter table.")
DEFINITIONS = {
    "time_to_notification_h": "Hours from result issued to patient notified (median, p90), among people who reached it inside the window.",
    "time_to_acknowledgement_h": "Hours from result issued to patient acknowledged (baseline: patient acts on the report).",
    "time_to_confirmation_d": "Days from result issued to clinician review of confirmation (confirmed or not confirmed).",
    "time_to_consultation_d": "Days from result issued to the specialist visit taking place.",
    "time_to_care_d": "Days from result issued to treatment started or surveillance agreed.",
    "referral_completion_rate": "Referral accepted, among people whose raised reading was confirmed.",
    "appointment_completion_rate": "Visit attended, among people with a booked appointment.",
    "treatment_initiation_rate": "Treatment started, among people who attended the visit.",
    "care_reached_rate": "Reached care (step 7) inside the window, among actionable people. Not one of the spec measures; used for the sensitivity analysis.",
    "unresolved_results": "Actionable people not in care and not clinically resolved as not confirmed at the end of the window, with the step where they stopped.",
    "teach_back_pass_rate": "Passed teach-back at the first try, among people who acknowledged. With-loop only.",
    "patient_confidence_mean": "Mean self-rated confidence 1 to 5 among people who acknowledged. With-loop only.",
    "plan_checkin_rate": "Weekly check-ins answered (done or partly) per week offered. With-loop only.",
    "re_engagement_after_lapse_rate": "People with a missed week who answered a check-in in the next two weeks. With-loop only.",
}


def _people(rows: list[dict]) -> dict:
    act = [r for r in rows if r["actionable"]]
    cols = {k: np.array([r[k] for r in act]) for k in ("age", "insurance_type", "preferred_language", "nationality_group", "sex", "age_band")}
    cols["severe"] = np.array([r["urgency"] == "SEVERE" for r in act], dtype=bool)
    return cols


def build(seed: int = DEFAULT_SEED, generated_at: str = FIXED_GENERATED_AT, size: int = COHORT_SIZE, write_dir: Path | None = DATA_DIR,
          with_sensitivity: bool = True) -> dict:
    params = pathway.load_params()
    rows_by_region = {r: cohort.generate_region(r, size, seed) for r in cohort.REGIONS}
    stats = {r: cohort.summary(rows) for r, rows in rows_by_region.items()}
    results = {}
    sens = {}
    for idx, region in enumerate(cohort.REGIONS):
        people = _people(rows_by_region[region])
        rnd = pathway.draws(len(people["age"]), [seed, idx, 99])
        results[region] = {}
        for arm in pathway.ARMS:
            out = pathway.simulate(people, region, params, arm, rnd)
            results[region][arm] = pathway.split_results(out, people, arm)
        if with_sensitivity:
            sens[region] = pathway.sensitivity(people, region, params, rnd)

    table = []
    for name, p in params["parameters"].items():
        arm, _, short = name.partition(".")
        table.append({"name": name, "arm": arm, "parameter": short, "value": p["value"], "unit": p["unit"],
                      "source": p["source"], "kind": p["kind"], "rationale": p["rationale"]})
    doc = {
        "metadata": {"seed": seed, "cohort_size_per_region": size, "generated_at": generated_at,
                     "cohort_summary": stats, "arms": list(pathway.ARMS), "regions": list(cohort.REGIONS),
                     "splits": list(pathway.SPLIT_FIELDS), "min_cell_size": pathway.MIN_CELL,
                     "disclaimer": DISCLAIMER, "measure_definitions": DEFINITIONS,
                     "reason_labels": pathway.REASON_LABELS, "simulated": True, "synthetic": True},
        "published_sources": params["published_sources"],
        "parameters": table,
        "results": results,
        "sensitivity": sens,
    }
    if write_dir is not None:
        write_dir = Path(write_dir)
        write_dir.mkdir(parents=True, exist_ok=True)
        for region, rows in rows_by_region.items():
            cohort.write_csv(rows, write_dir / f"cohort_{region.lower()}.csv")
        _write(write_dir / "simulation_results.json", json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
        _write(write_dir / "demo_series.json", json.dumps(demo_series.build(seed), indent=1, ensure_ascii=False) + "\n")
        _write(write_dir / "DATA_CARD.md", datacard.build(seed, stats))
    return doc


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:  # LF on every platform
        f.write(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--generated-at", default=FIXED_GENERATED_AT)
    ap.add_argument("--out-dir", type=Path, default=DATA_DIR)
    args = ap.parse_args()
    doc = build(args.seed, args.generated_at, write_dir=args.out_dir)
    for region in cohort.REGIONS:
        for arm in pathway.ARMS:
            m = doc["results"][region][arm]["none"]["all"]
            print(region, arm, "actionable", m["n_actionable"], "care_rate", m["care_reached_rate"]["value"],
                  "median_time_to_care_d", m["time_to_care_d"]["median"], "unresolved_rate", m["unresolved_results"]["rate"])
    print("wrote", args.out_dir)


if __name__ == "__main__":
    main()
