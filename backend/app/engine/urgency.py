"""Urgency classification and blood pressure confirmation rules.

Routing and urgency are decided here from numbers only. No model output is read.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from typing import Sequence

from . import config as cfg
from .types import ConfirmationMethod, ConfirmationStatus, ReadingData, ReadingSource, Severity


def classify(systolic: int, diastolic: int) -> Severity | None:
    """SEVERE, RAISED, or None when the reading is not actionable."""
    if systolic >= cfg.value("thresholds", "severe_systolic") or diastolic >= cfg.value("thresholds", "severe_diastolic"):
        return Severity.SEVERE
    if systolic >= cfg.value("thresholds", "raised_systolic") or diastolic >= cfg.value("thresholds", "raised_diastolic"):
        return Severity.RAISED
    return None


@dataclass(frozen=True)
class Confirmation:
    status: ConfirmationStatus
    average_systolic: float | None
    average_diastolic: float | None
    days_counted: int
    readings_used: int
    days_with_enough_readings: int
    days_required: int


def _local(moment: datetime, tz: tzinfo | None) -> datetime:
    """The reading time on the patient's local clock. `tz` is passed in by the caller; None means UTC."""
    return moment.astimezone(tz or timezone.utc)


def evaluate_hbpm(readings: Sequence[ReadingData], tz: tzinfo | None = None) -> Confirmation:
    """Home average: days with enough readings, first such day discarded, rest averaged.

    Days are calendar days on the patient's local clock (`tz`). Too few days is INSUFFICIENT, never NOT_CONFIRMED.
    """
    min_days = int(cfg.value("thresholds", "hbpm_min_days"))
    min_per_day = int(cfg.value("thresholds", "hbpm_min_readings_per_day"))
    by_day: dict = defaultdict(list)
    for r in readings:
        if r.source == ReadingSource.HOME_CUFF:
            by_day[_local(r.taken_at, tz).date()].append(r)
    qualifying = sorted(d for d, rs in by_day.items() if len(rs) >= min_per_day)
    if len(qualifying) < min_days:
        return Confirmation(ConfirmationStatus.INSUFFICIENT, None, None, 0, 0, len(qualifying), min_days)
    used = [r for d in qualifying[1:] for r in by_day[d]]
    return _decide(used, len(qualifying) - 1, len(qualifying), min_days, "hbpm")


def evaluate_abpm(readings: Sequence[ReadingData], tz: tzinfo | None = None) -> Confirmation:
    """Daytime average of ambulatory readings. The daytime window is on the patient's local clock (`tz`)."""
    start = int(cfg.value("thresholds", "abpm_daytime_start_hour"))
    end = int(cfg.value("thresholds", "abpm_daytime_end_hour"))
    needed = int(cfg.value("thresholds", "abpm_min_daytime_readings"))
    day = [r for r in readings if r.source == ReadingSource.ABPM and start <= _local(r.taken_at, tz).hour < end]
    if len(day) < needed:
        return Confirmation(ConfirmationStatus.INSUFFICIENT, None, None, 0, len(day), 0, needed)
    return _decide(day, 1, 1, needed, "abpm")


def _decide(used: Sequence[ReadingData], days_counted: int, qualifying: int, required: int, kind: str) -> Confirmation:
    avg_s = sum(r.systolic for r in used) / len(used)
    avg_d = sum(r.diastolic for r in used) / len(used)
    sys_t = cfg.value("thresholds", f"{kind}_systolic" if kind == "hbpm" else "abpm_daytime_systolic")
    dia_t = cfg.value("thresholds", f"{kind}_diastolic" if kind == "hbpm" else "abpm_daytime_diastolic")
    raised = avg_s >= sys_t or avg_d >= dia_t
    status = ConfirmationStatus.CONFIRMED_RAISED if raised else ConfirmationStatus.NOT_CONFIRMED
    return Confirmation(status, round(avg_s, 1), round(avg_d, 1), days_counted, len(used), qualifying, required)


def evaluate_confirmation(method: ConfirmationMethod | None, readings: Sequence[ReadingData],
                          tz: tzinfo | None = None) -> Confirmation | None:
    if method == ConfirmationMethod.HBPM:
        return evaluate_hbpm(readings, tz)
    if method == ConfirmationMethod.ABPM:
        return evaluate_abpm(readings, tz)
    return None


def at_target(readings: Sequence[ReadingData]) -> bool:
    """True when the last N clinic readings are all below the target values."""
    n = int(cfg.value("thresholds", "target_consecutive_readings"))
    clinic = sorted((r for r in readings if r.source == ReadingSource.CLINIC), key=lambda r: r.taken_at)
    last = clinic[-n:]
    if len(last) < n:
        return False
    sys_t = cfg.value("thresholds", "target_systolic")
    dia_t = cfg.value("thresholds", "target_diastolic")
    return all(r.systolic < sys_t and r.diastolic < dia_t for r in last)
