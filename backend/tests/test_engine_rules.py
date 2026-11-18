"""Pure engine tests: thresholds, confirmation averages, SLA, escalation, unreachable protocol, plan rules."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import engine
from app.engine import plan as plan_rules
from app.engine.types import (
    Action, CaseData, CheckinStatus, ConfirmationStatus, EffectKind, ReadingData, ReadingSource, ReferralStatus, Role, Severity, State,
)
from app.engine.urgency import classify, evaluate_hbpm

T0 = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
BACKEND = Path(__file__).resolve().parents[1]


def case(**kw) -> CaseData:
    base = dict(
        state=State.NOTIFIED, severity=Severity.RAISED, urgent=False, urgent_started_at=None, urgent_review_done=False,
        urgent_review_escalated=False, step_started_at=T0, owner_user_id=1, referral_status=None, referral_to_user_id=None,
        appointment_at=None, confirmation_method=None, confirmation_status=None, not_confirmed_reviewed=False, closure_ready=False,
        share_consent_granted=True, escalation_level=0, unreachable_stage=0, needs_clinician_decision=False,
    )
    base.update(kw)
    return CaseData(**base)


# ---------------------------------------------------------------- thresholds


@pytest.mark.parametrize("sys_,dia,expected", [
    (179, 109, Severity.RAISED), (180, 80, Severity.SEVERE), (150, 110, Severity.SEVERE), (185, 115, Severity.SEVERE),
    (139, 89, None), (140, 80, Severity.RAISED), (120, 90, Severity.RAISED), (140, 90, Severity.RAISED),
])
def test_classification_boundaries(sys_, dia, expected):
    assert classify(sys_, dia) == expected


def readings(per_day: list[tuple[int, int]], days: int, source=ReadingSource.HOME_CUFF) -> list[ReadingData]:
    out = []
    for d in range(days):
        for i, (s, dia) in enumerate(per_day):
            out.append(ReadingData(s, dia, T0 + timedelta(days=d, hours=i * 12), source))
    return out


def test_hbpm_average_at_threshold_is_raised():
    # day 1 is discarded; later days average exactly 135/85
    rs = readings([(135, 85), (135, 85)], 4)
    r = evaluate_hbpm(rs)
    assert r.status is ConfirmationStatus.CONFIRMED_RAISED and (r.average_systolic, r.average_diastolic) == (135, 85)


def test_hbpm_just_under_is_not_confirmed():
    r = evaluate_hbpm(readings([(134, 84), (134, 84)], 4))
    assert r.status is ConfirmationStatus.NOT_CONFIRMED


def test_hbpm_just_over_is_raised():
    r = evaluate_hbpm(readings([(136, 84), (136, 84)], 4))
    assert r.status is ConfirmationStatus.CONFIRMED_RAISED


def test_hbpm_first_day_is_discarded():
    rs = readings([(190, 120), (190, 120)], 1) + [
        ReadingData(120, 78, T0 + timedelta(days=d, hours=h), ReadingSource.HOME_CUFF) for d in range(1, 4) for h in (0, 12)]
    r = evaluate_hbpm(rs)
    assert r.status is ConfirmationStatus.NOT_CONFIRMED and r.average_systolic == 120


def test_hbpm_too_few_days_is_insufficient_not_negative():
    r = evaluate_hbpm(readings([(120, 70), (120, 70)], 3))
    assert r.status is ConfirmationStatus.INSUFFICIENT


def test_hbpm_days_with_one_reading_do_not_count():
    rs = readings([(150, 95)], 8)
    assert evaluate_hbpm(rs).status is ConfirmationStatus.INSUFFICIENT


def test_wearable_is_not_a_reading_source():
    assert {s.value for s in ReadingSource} == {"HOME_CUFF", "CLINIC", "ABPM"}


def test_abpm_daytime_average():
    def abpm(sys_, n=14):
        return [ReadingData(sys_, 80, T0.replace(hour=7) + timedelta(minutes=50 * i), ReadingSource.ABPM) for i in range(n)]
    assert engine.urgency.evaluate_abpm(abpm(135)).status is ConfirmationStatus.CONFIRMED_RAISED
    assert engine.urgency.evaluate_abpm(abpm(134)).status is ConfirmationStatus.NOT_CONFIRMED
    assert engine.urgency.evaluate_abpm(abpm(150, n=5)).status is ConfirmationStatus.INSUFFICIENT


# ---------------------------------------------------------------- config and closure table


def test_every_config_entry_is_a_labelled_placeholder():
    entries = engine.config.all_entries()
    assert len(entries) > 30
    for e in entries:
        assert e.status == "placeholder_pending_clinician_signoff" and e.basis.strip() and e.unit


def test_only_close_can_produce_closed():
    assert engine.producers_of_closed() == {Action.CLOSE}
    for action, table in engine.TRANSITIONS.items():
        if action is not Action.CLOSE:
            assert State.CLOSED not in table.values()
    # and the effect kinds the SLA engine can emit contain nothing that closes a case
    assert not any("CLOSE" in k.value for k in EffectKind)


def test_close_rule_allows_only_clinicians():
    c = case()
    for role in (Role.PATIENT, Role.COORDINATOR, Role.ANALYST, Role.SYSTEM):
        assert engine.check(Action.CLOSE, role, c).status == 403
    assert engine.check(Action.CLOSE, Role.CLINICIAN, c).ok


def test_closure_gate_unit():
    v = engine.validate_closure
    assert v(Role.CLINICIAN, "BP_CONTROLLED", None, None).status == 422
    assert v(Role.CLINICIAN, "BP_CONTROLLED", None, "too short").status == 422
    assert v(Role.CLINICIAN, "BP_CONTROLLED", "  ", "123456789").status == 422  # nine characters
    assert v(Role.CLINICIAN, None, "ref", None).status == 422
    assert v(Role.CLINICIAN, "MADE_UP", "ref", None).status == 422
    assert v(Role.CLINICIAN, "BP_CONTROLLED", "reading:12", None).ok
    assert v(Role.CLINICIAN, "OTHER_CLINICAL_DECISION", None, "1234567890").ok
    assert v(Role.COORDINATOR, "BP_CONTROLLED", "reading:12", None).status == 403


# ---------------------------------------------------------------- SLA and escalation


def test_overdue_after_due_time_and_level_1():
    c = case()  # NOTIFIED, 72 h
    assert not engine.evaluate(c, T0 + timedelta(hours=72)).overdue
    ev = engine.evaluate(c, T0 + timedelta(hours=72, seconds=1))
    assert ev.overdue and ev.escalation_level == 1
    assert [e.kind for e in ev.effects if e.kind.name.startswith("ESCALATE")] == [EffectKind.ESCALATE_LEVEL_1]


def test_level_2_at_twice_the_service_level():
    c = case()
    assert engine.evaluate(c, T0 + timedelta(hours=143)).escalation_level == 1
    ev = engine.evaluate(c, T0 + timedelta(hours=144, seconds=1))
    assert ev.escalation_level == 2 and ev.escalation_target == "coordinator_lead"


def test_severe_level_2_at_one_times_and_targets_on_call_clinician():
    c = case(state=State.RESULT_ISSUED, severity=Severity.SEVERE)  # 2 h service level
    ev = engine.evaluate(c, T0 + timedelta(hours=2, seconds=1))
    assert ev.escalation_level == 2 and ev.escalation_target == "on_call_clinician"


def test_urgent_review_task_escalates_at_its_due_time():
    c = case(urgent=True, urgent_started_at=T0, severity=Severity.SEVERE)
    before = engine.evaluate(c, T0 + timedelta(hours=3, minutes=59))
    assert EffectKind.ESCALATE_URGENT_REVIEW not in [e.kind for e in before.effects]
    after = engine.evaluate(c, T0 + timedelta(hours=4, seconds=1))
    assert EffectKind.ESCALATE_URGENT_REVIEW in [e.kind for e in after.effects]
    done = engine.evaluate(case(urgent=True, urgent_started_at=T0, urgent_review_done=True), T0 + timedelta(hours=9))
    assert EffectKind.ESCALATE_URGENT_REVIEW not in [e.kind for e in done.effects]


def test_notification_step_keeps_normal_pathway_when_urgent():
    step = engine.next_step(case(state=State.RESULT_ISSUED, severity=Severity.SEVERE, urgent=True, urgent_started_at=T0))
    assert step.label_key == "notify_patient" and step.service_level_h == 2


def test_effects_are_not_repeated():
    c = case(escalation_level=2, unreachable_stage=4)
    assert engine.evaluate(c, T0 + timedelta(days=30)).effects == ()


@pytest.mark.parametrize("hours,kinds", [
    (23, []), (24, [EffectKind.UNREACHABLE_REMINDER]),
    (48, [EffectKind.UNREACHABLE_REMINDER, EffectKind.UNREACHABLE_SECOND_CHANNEL]),
    (72, [EffectKind.UNREACHABLE_REMINDER, EffectKind.UNREACHABLE_SECOND_CHANNEL, EffectKind.UNREACHABLE_CALL_TASK]),
    (120, [EffectKind.UNREACHABLE_REMINDER, EffectKind.UNREACHABLE_SECOND_CHANNEL, EffectKind.UNREACHABLE_CALL_TASK,
           EffectKind.UNREACHABLE_CLINICIAN_DECISION]),
])
def test_unreachable_protocol_ladder(hours, kinds):
    ev = engine.evaluate(case(), T0 + timedelta(hours=hours))
    assert [e.kind for e in ev.effects if e.kind.name.startswith("UNREACHABLE")] == kinds


def test_protocol_exhausted_never_closes():
    ev = engine.evaluate(case(), T0 + timedelta(days=60))
    assert ev.next_step is not None  # the case is still open; only a flag for a clinician decision is raised


def test_next_step_owners_and_levels():
    assert engine.next_step(case(state=State.CONFIRMED, referral_status=ReferralStatus.REJECTED, owner_user_id=None)).label_key == "reassign_or_rerefer"
    accepted = engine.next_step(case(state=State.REFERRED, referral_status=ReferralStatus.ACCEPTED))
    assert accepted.owner_role is Role.COORDINATOR and accepted.service_level_h == 120
    pending = engine.next_step(case(state=State.REFERRED, referral_status=ReferralStatus.PENDING))
    assert pending.owner_role is Role.CLINICIAN and pending.service_level_h == 48
    nc = engine.next_step(case(state=State.ACKNOWLEDGED, not_confirmed_reviewed=True))
    assert nc.label_key == "clinician_closure_decision" and nc.service_level_h == 72
    assert engine.next_step(case(state=State.CLOSED)) is None


# ---------------------------------------------------------------- lifestyle plan


def week(status, size=plan_rules.PlanSize.FULL, action=plan_rules.PlanActionKey.SALT, offered=False):
    return plan_rules.PlanWeekData(action, size, status, offered)


def test_missed_week_shrinks_and_is_no_blame():
    d = plan_rules.decide_next([week(CheckinStatus.MISSED)])
    assert d.size == plan_rules.PlanSize.SMALLER and d.shrunk and "no_blame_checkin" in d.message_keys and d.action_key == plan_rules.PlanActionKey.SALT


def test_smallest_never_goes_below_smallest_or_resets():
    d = plan_rules.decide_next([week(CheckinStatus.MISSED, plan_rules.PlanSize.SMALLEST)])
    assert d.size == plan_rules.PlanSize.SMALLEST and not d.shrunk


def test_two_partly_in_a_row_shrinks_one_does_not():
    assert plan_rules.decide_next([week(CheckinStatus.PARTLY)]).size == plan_rules.PlanSize.FULL
    d = plan_rules.decide_next([week(CheckinStatus.PARTLY), week(CheckinStatus.PARTLY)])
    assert d.size == plan_rules.PlanSize.SMALLER


def test_two_done_offers_larger_never_forces():
    s = plan_rules.PlanSize.SMALLEST
    d = plan_rules.decide_next([week(CheckinStatus.DONE, s), week(CheckinStatus.DONE, s)])
    assert d.offer_larger and d.size == s and not d.enlarged
    accepted = plan_rules.decide_next([week(CheckinStatus.DONE, s), week(CheckinStatus.DONE, s, offered=True)], accept_larger=True)
    assert accepted.enlarged and accepted.size == plan_rules.PlanSize.SMALLER


def test_three_missed_create_a_call_offer():
    ms = [week(CheckinStatus.MISSED, plan_rules.PlanSize.SMALLEST) for _ in range(3)]
    assert plan_rules.decide_next(ms[:2]).call_offer is False
    assert plan_rules.decide_next(ms).call_offer is True
    assert plan_rules.decide_next([*ms, week(CheckinStatus.DONE, plan_rules.PlanSize.SMALLEST)]).call_offer is False


def test_week_lapses_only_after_grace_period():
    assert not plan_rules.week_lapsed(T0, T0 + timedelta(days=8))
    assert plan_rules.week_lapsed(T0, T0 + timedelta(days=8, seconds=1))


# ---------------------------------------------------------------- engine isolation


def test_engine_imports_nothing_from_wording_or_io():
    code = (
        "import sys, app.engine, app.engine.sla, app.engine.plan, app.engine.actions, app.engine.queues, app.engine.closure\n"
        "bad = [m for m in sys.modules if m.startswith(('app.wording', 'app.api', 'app.db', 'sqlalchemy', 'fastapi'))]\n"
        "assert not bad, bad"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_engine_source_never_mentions_wording():
    for path in (BACKEND / "app" / "engine").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "app.wording" not in text and "from app import wording" not in text, path.name
