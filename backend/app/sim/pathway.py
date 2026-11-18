"""Monte Carlo simulation of the eight-step pathway for the actionable subset, under two arms.

Arms: `baseline` (result report only, no owner, no reminders) and `with_loop`.
Every probability and delay comes from params.yaml. Both arms share the same random draws per person
(common random numbers), so differences between arms come from parameters and not from luck.

These are simulated results on synthetic people. They show what the system measures. They are not
evidence of clinical effectiveness.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

PARAMS_PATH = Path(__file__).with_name("params.yaml")
ARMS = ("baseline", "with_loop")
MIN_CELL = 5
SPLIT_FIELDS = {"none": None, "language": "preferred_language", "nationality_group": "nationality_group",
                "sex": "sex", "age_band": "age_band"}
N_U, N_Z, PLAN_WEEKS_MAX = 14, 14, 12

REASON_LABELS = {
    "result_not_delivered": "Result not delivered in time",
    "no_acknowledgement": "Patient did not acknowledge in time",
    "confirmation_not_completed": "Confirmation by home or 24-hour monitoring not completed in time",
    "referral_not_sent": "Referral not sent in time",
    "referral_not_accepted": "Referral not accepted in time",
    "appointment_not_booked": "Appointment not booked in time",
    "visit_not_attended": "Visit not attended in time",
    "care_not_recorded": "Visit outcome not recorded in time",
}


def load_params(path: Path = PARAMS_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def val(params: dict, arm: str, name: str):
    table = params["parameters"]
    for key in (f"{arm}.{name}", f"common.{name}"):
        if key in table:
            return table[key]["value"]
    raise KeyError(f"{arm}.{name}")


def draws(n: int, seed_seq: list[int]) -> dict:
    """Random numbers for n people, shared by both arms."""
    rng = np.random.default_rng(seed_seq)
    return {"U": rng.random((n, N_U)), "Z": rng.standard_normal((n, N_Z)), "P": rng.random((n, PLAN_WEEKS_MAX, 2))}


def simulate(people: dict, region: str, params: dict, arm: str, rnd: dict, with_plan: bool = True) -> dict:
    """people: arrays age, insurance_type, severe for the actionable subset. Returns per-person outcome arrays."""
    U, Z = rnd["U"], rnd["Z"]
    n = len(people["age"])
    loop = arm == "with_loop"
    window = params["parameters"]["simulation.follow_up_days"]["value"]
    v = lambda name: val(params, arm, name)  # noqa: E731

    m_age = np.where(people["age"] >= 65, v("modifier_age_65_plus"), 1.0)
    m_cost = np.where(people["insurance_type"] == "none", v("modifier_uninsured_cover_shown") if loop else v("modifier_uninsured"), 1.0)
    m_reg = v("modifier_yde_access") if region == "YDE" else 1.0
    m_sev = np.where(people["severe"], v("severe_delay_multiplier"), 1.0) if loop else 1.0

    alive = np.ones(n, dtype=bool)
    t = np.zeros(n)
    reason = np.full(n, "", dtype=object)
    times: dict[str, np.ndarray] = {}
    flags: dict[str, np.ndarray] = {}

    def advance(key, why, ui, p, prefix, zi, dmult=1.0):
        nonlocal alive, t
        td = t + v(f"{prefix}_median_d") * np.exp(v(f"{prefix}_sigma") * Z[:, zi]) * dmult
        ok = alive & (U[:, ui] < np.clip(p, 0, 1)) & (td <= window)
        reason[alive & ~ok] = why
        alive = ok
        t = np.where(ok, td, t)
        times[key] = np.where(ok, td, np.nan)
        flags[key] = ok.copy()

    advance("notified", "result_not_delivered", 0, v("p_notified"), "notify_delay", 0, m_sev)
    advance("acknowledged", "no_acknowledgement", 1, v("p_acknowledged") * m_age, "ack_delay", 1, m_sev)
    advance("reviewed", "confirmation_not_completed", 2, v("p_confirmation_completed") * m_age, "confirm_delay", 2)
    raised = U[:, 3] < v("p_confirmed_raised")
    not_confirmed = alive & ~raised
    alive = alive & raised
    flags["not_confirmed"] = not_confirmed
    flags["confirmed"] = alive.copy()
    advance("referral_sent", "referral_not_sent", 4, v("p_referral_sent"), "referral_delay", 4)
    advance("referral_accepted", "referral_not_accepted", 5, v("p_referral_accepted") * m_reg, "accept_delay", 5)
    advance("booked", "appointment_not_booked", 6, v("p_appointment_booked") * m_age * m_cost * m_reg, "book_delay", 6)
    advance("attended", "visit_not_attended", 7, v("p_visit_attended") * m_age * m_cost, "visit_wait", 7)
    advance("care", "care_not_recorded", 8, v("p_care_recorded"), "care_delay", 8)
    treated = alive & (U[:, 9] < v("p_treatment_started"))
    # closure is a clinician action; the simulation only asks whether one is recorded inside the window
    t_close = t + v("close_delay_median_d") * np.exp(v("close_delay_sigma") * Z[:, 10])
    closed = alive & (U[:, 10] < v("p_closed")) & (t_close <= window)

    resolved = flags["care"] | not_confirmed
    out = {
        "times": times, "flags": flags, "treated": treated, "closed": closed, "resolved": resolved,
        "reason": np.where(resolved, "", reason),
        "ack_first_pass": np.zeros(n, dtype=bool), "confidence": np.zeros(n),
        "plan_offered": np.zeros(n, dtype=int), "plan_responded": np.zeros(n, dtype=int),
        "lapse_evaluable": np.zeros(n, dtype=bool), "lapse_engaged": np.zeros(n, dtype=bool),
    }
    if loop:
        ack = flags["acknowledged"]
        out["ack_first_pass"] = ack & (U[:, 11] < v("p_teach_back_first_pass"))
        cum = np.cumsum(v("confidence_probs_1_to_5"))
        out["confidence"] = np.where(ack, 1 + np.minimum(np.searchsorted(cum, U[:, 13], side="right"), 4), 0)
        if with_plan:
            _simulate_plan(out, flags["care"], times["care"], window, rnd["P"], v, int(params["parameters"]["simulation.plan_weeks"]["value"]))
    return out


def _simulate_plan(out, in_care, t_care, window, P, v, plan_weeks) -> None:
    """Weekly lifestyle plan. Missed or two partly in a row -> smaller size. Two done -> larger size offered.
    No streaks, no resets. Three missed in a row -> coordinator call task (human), which may bring the person back."""
    n = len(in_care)
    avail = np.where(in_care, np.clip(np.floor((window - np.nan_to_num(t_care)) / 7), 0, plan_weeks), 0).astype(int)
    pd, pp = np.array(v("plan_p_done_by_size")), np.array(v("plan_p_partly_by_size"))
    size = np.zeros(n, dtype=int)
    cp = np.zeros(n, dtype=int)
    cm = np.zeros(n, dtype=int)
    cd = np.zeros(n, dtype=int)
    boost = np.zeros(n, dtype=bool)
    hist = np.full((n, plan_weeks), -1)
    for w in range(plan_weeks):
        act = w < avail
        u1, u2 = P[:, w, 0], P[:, w, 1]
        a, b = pd[size], pp[size]
        status = np.where(u1 < a, 0, np.where(u1 < a + b, 1, 2))
        status = np.where(boost & (status == 2), 1, status)
        hist[:, w] = np.where(act, status, -1)
        done, part, miss = act & (status == 0), act & (status == 1), act & (status == 2)
        cm = np.where(miss, cm + 1, np.where(act, 0, cm))
        cp = np.where(part, cp + 1, np.where(act, 0, cp))
        cd = np.where(done, cd + 1, np.where(act, 0, cd))
        shrink = miss | (part & (cp >= 2))
        size = np.where(shrink, np.minimum(size + 1, 2), size)
        cp = np.where(part & (cp >= 2), 0, cp)
        grow = done & (cd >= 2) & (u2 < v("plan_p_accept_larger"))
        size = np.where(grow, np.maximum(size - 1, 0), size)
        cd = np.where(done & (cd >= 2), 0, cd)
        call = act & (cm >= 3)
        boost = call & (u2 < v("plan_p_reengage_after_call"))
        cm = np.where(call, 0, cm)
    out["plan_offered"] = (hist >= 0).sum(axis=1)
    out["plan_responded"] = ((hist == 0) | (hist == 1)).sum(axis=1)
    for i in np.nonzero(avail > 0)[0]:
        row = hist[i]
        starts = [w for w in range(avail[i]) if row[w] == 2 and (w == 0 or row[w - 1] != 2)]
        if starts and starts[0] + 1 < avail[i]:
            w = starts[0]
            out["lapse_evaluable"][i] = True
            out["lapse_engaged"][i] = bool(np.isin(row[w + 1:w + 3], (0, 1)).any())




# ---------------------------------------------------------------- measures

def _r(x, d=2):
    return None if x is None else round(float(x), d)


def _time(vals: np.ndarray, scale: float = 1.0, unit: str = "days") -> dict:
    vals = vals[~np.isnan(vals)] * scale
    n = int(len(vals))
    if n < MIN_CELL:
        return {"n": n, "suppressed": True, "median": None, "p90": None, "unit": unit}
    return {"n": n, "suppressed": False, "median": _r(np.median(vals)), "p90": _r(np.percentile(vals, 90)), "unit": unit}


def _rate(num: int, den: int) -> dict:
    num, den = int(num), int(den)
    if den < MIN_CELL:
        return {"n": den, "suppressed": True, "numerator": None, "value": None}
    return {"n": den, "suppressed": False, "numerator": num, "value": _r(num / den, 4)}


def _not_measured(note: str) -> dict:
    return {"n": 0, "suppressed": True, "value": None, "note": note}


def measures(out: dict, mask: np.ndarray, arm: str) -> dict:
    f, t = out["flags"], out["times"]
    n = int(mask.sum())
    unresolved = mask & ~out["resolved"]
    reasons = {}
    for key in REASON_LABELS:
        c = int((unresolved & (out["reason"] == key)).sum())
        reasons[key] = {"label": REASON_LABELS[key], "count": None if c < MIN_CELL else c, "suppressed": c < MIN_CELL}
    unres_count = int(unresolved.sum())
    loop = arm == "with_loop"
    ack = mask & f["acknowledged"]
    conf_n = int(ack.sum())
    care = mask & f["care"]
    res = {
        "n_actionable": n,
        "time_to_notification_h": _time(np.where(mask, t["notified"], np.nan), 24, "hours"),
        "time_to_acknowledgement_h": _time(np.where(mask, t["acknowledged"], np.nan), 24, "hours"),
        "time_to_confirmation_d": _time(np.where(mask, t["reviewed"], np.nan)),
        "time_to_consultation_d": _time(np.where(mask, t["attended"], np.nan)),
        "time_to_care_d": _time(np.where(mask, t["care"], np.nan)),
        "referral_completion_rate": _rate((mask & f["referral_accepted"]).sum(), (mask & f["confirmed"]).sum()),
        "appointment_completion_rate": _rate((mask & f["attended"]).sum(), (mask & f["booked"]).sum()),
        "treatment_initiation_rate": _rate((mask & out["treated"]).sum(), (mask & f["attended"]).sum()),
        "care_reached_rate": _rate(care.sum(), n),
        "unresolved_results": (
            {"n": n, "suppressed": True, "count": None, "rate": None}
            if n < MIN_CELL else
            {"n": n, "suppressed": False, "count": unres_count, "rate": _r(unres_count / n, 4)}
        ) | {"delay_reasons": reasons},
    }
    if loop:
        res["teach_back_pass_rate"] = _rate((mask & out["ack_first_pass"]).sum(), conf_n)
        res["patient_confidence_mean"] = (
            {"n": conf_n, "suppressed": True, "value": None} if conf_n < MIN_CELL
            else {"n": conf_n, "suppressed": False, "value": _r(out["confidence"][ack].mean(), 2)})
        res["plan_checkin_rate"] = _rate(out["plan_responded"][mask].sum(), out["plan_offered"][mask].sum())
        res["re_engagement_after_lapse_rate"] = _rate((mask & out["lapse_engaged"]).sum(), (mask & out["lapse_evaluable"]).sum())
    else:
        note = "Not measured in the baseline arm: it has no teach-back, plan or check-ins."
        for k in ("teach_back_pass_rate", "patient_confidence_mean", "plan_checkin_rate", "re_engagement_after_lapse_rate"):
            res[k] = _not_measured(note)
    return res


def split_results(out: dict, people: dict, arm: str) -> dict:
    n = len(people["age"])
    result = {}
    for split, field in SPLIT_FIELDS.items():
        if field is None:
            result[split] = {"all": measures(out, np.ones(n, dtype=bool), arm)}
        else:
            col = people[field]
            result[split] = {str(g): measures(out, col == g, arm) for g in sorted(set(col.tolist()))}
    return result


# ---------------------------------------------------------------- sensitivity

def _headline(people, region, params, rnd) -> dict:
    out = {}
    for arm in ARMS:
        r = simulate(people, region, params, arm, rnd, with_plan=False)
        care = r["flags"]["care"]
        tc = r["times"]["care"][care]
        out[arm] = {"care_reached_rate": float(care.mean()), "median_time_to_care_d": float(np.median(tc)) if len(tc) else None}
    out["care_rate_difference"] = out["with_loop"]["care_reached_rate"] - out["baseline"]["care_reached_rate"]
    return out


def _scaled(params: dict, name: str, factor: float) -> dict:
    p = {**params, "parameters": {k: dict(x) for k, x in params["parameters"].items()}}
    old = p["parameters"][name]["value"]
    new = old * factor
    if p["parameters"][name]["unit"] == "probability":
        new = min(new, 0.99)
    p["parameters"][name]["value"] = new
    return p


def sensitivity(people: dict, region: str, params: dict, rnd: dict, factor: float = 0.2, top: int = 3) -> dict:
    """One-way: scale each assumption by (1 - factor) and (1 + factor), rank by swing in the with-loop minus
    baseline difference in share reaching care, then report low/base/high for the top three."""
    candidates = [k for k, x in params["parameters"].items()
                  if x["kind"] == "assumption" and not isinstance(x["value"], list)
                  and (x["unit"] == "probability" or k.endswith("_median_d"))
                  and k.split(".")[0] in ("baseline", "with_loop", "common")]
    base = _headline(people, region, params, rnd)
    ranking = []
    for k in candidates:
        lo = _headline(people, region, _scaled(params, k, 1 - factor), rnd)
        hi = _headline(people, region, _scaled(params, k, 1 + factor), rnd)
        ranking.append((abs(hi["care_rate_difference"] - lo["care_rate_difference"]), k, lo, hi))
    ranking.sort(key=lambda r: (-r[0], r[1]))
    table = [{"parameter": k, "swing_in_care_rate_difference": _r(s, 4)} for s, k, _, _ in ranking[:10]]

    def fmt(h):
        return {"baseline_care_reached_rate": _r(h["baseline"]["care_reached_rate"], 4),
                "with_loop_care_reached_rate": _r(h["with_loop"]["care_reached_rate"], 4),
                "difference": _r(h["care_rate_difference"], 4),
                "baseline_median_time_to_care_d": _r(h["baseline"]["median_time_to_care_d"]),
                "with_loop_median_time_to_care_d": _r(h["with_loop"]["median_time_to_care_d"])}

    detail = []
    for s, k, lo, hi in ranking[:top]:
        x = params["parameters"][k]
        low_v, high_v = _r(min(x["value"] * (1 - factor), 0.99 if x["unit"] == "probability" else 1e9), 4), _r(min(x["value"] * (1 + factor), 0.99 if x["unit"] == "probability" else 1e9), 4)
        detail.append({"parameter": k, "base_value": x["value"], "low_value": low_v, "high_value": high_v,
                       "low": fmt(lo), "base": fmt(base), "high": fmt(hi)})
    return {"outcome": "Share of actionable people who reach care (step 7) inside the follow-up window, and the difference between arms",
            "method": f"One-way: each assumed probability or median delay scaled by minus and plus {int(factor * 100)} percent (probabilities capped at 0.99), others at base value. Published values are not varied.",
            "ranking_top10": table, "top3": detail}
