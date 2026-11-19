"""Enumerations and plain data carriers shared by the engine and the API layer.

The engine never touches a database. The API builds a `CaseData` snapshot from rows,
asks the engine what is allowed and what is due, then writes the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class State(StrEnum):
    RESULT_ISSUED = "RESULT_ISSUED"
    NOTIFIED = "NOTIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CONFIRMED = "CONFIRMED"
    REFERRED = "REFERRED"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    IN_CARE = "IN_CARE"
    CLOSED = "CLOSED"


STATE_ORDER: tuple[State, ...] = tuple(State)
OPEN_STATES: frozenset[State] = frozenset(State) - {State.CLOSED}


def state_index(state: State) -> int:
    return STATE_ORDER.index(state)


class Role(StrEnum):
    PATIENT = "patient"
    COORDINATOR = "coordinator"
    CLINICIAN = "clinician"
    ANALYST = "analyst"
    SYSTEM = "system"


class Action(StrEnum):
    NOTIFY = "notify"
    ACKNOWLEDGE = "acknowledge"
    CHOOSE_CONFIRMATION = "choose_confirmation"
    ADD_READING = "add_reading"
    REVIEW_CONFIRMATION = "review_confirmation"
    REFER = "refer"
    ACCEPT_REFERRAL = "accept_referral"
    REJECT_REFERRAL = "reject_referral"
    ASSIGN_OWNER = "assign_owner"
    BOOK_APPOINTMENT = "book_appointment"
    RECORD_VISIT = "record_visit"
    PLAN_CHECKIN = "plan_checkin"
    ESCALATE = "escalate"
    CLOSE = "close"
    REOPEN = "reopen"
    UPDATE_CONSENT = "update_consent"
    COMPLETE_URGENT_REVIEW = "complete_urgent_review"


class Severity(StrEnum):
    RAISED = "RAISED"
    SEVERE = "SEVERE"


class ReferralStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ConfirmationMethod(StrEnum):
    HBPM = "HBPM"
    ABPM = "ABPM"


class ConfirmationStatus(StrEnum):
    CONFIRMED_RAISED = "CONFIRMED_RAISED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    INSUFFICIENT = "INSUFFICIENT"


class ReadingSource(StrEnum):
    """Blood pressure values come only from a validated cuff or ambulatory monitor. There is no wearable source."""

    HOME_CUFF = "HOME_CUFF"
    CLINIC = "CLINIC"
    ABPM = "ABPM"


class ClosureEvidence(StrEnum):
    BP_CONTROLLED = "BP_CONTROLLED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    CARE_TRANSFERRED = "CARE_TRANSFERRED"
    PATIENT_DECLINED = "PATIENT_DECLINED"
    UNREACHABLE_AFTER_PROTOCOL = "UNREACHABLE_AFTER_PROTOCOL"
    DECEASED_OR_MOVED = "DECEASED_OR_MOVED"
    OTHER_CLINICAL_DECISION = "OTHER_CLINICAL_DECISION"


class EventType(StrEnum):
    CASE_OPENED = "CASE_OPENED"
    CASE_VIEWED = "CASE_VIEWED"
    STATE_CHANGED = "STATE_CHANGED"
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    MESSAGE_SUPPRESSED = "MESSAGE_SUPPRESSED"
    TEACH_BACK_PASSED = "TEACH_BACK_PASSED"
    TEACH_BACK_FAILED = "TEACH_BACK_FAILED"
    RED_FLAG_REPORTED = "RED_FLAG_REPORTED"
    URGENT_FLAGGED = "URGENT_FLAGGED"
    URGENT_REVIEW_COMPLETED = "URGENT_REVIEW_COMPLETED"
    CONFIRMATION_CHOSEN = "CONFIRMATION_CHOSEN"
    READING_ADDED = "READING_ADDED"
    CONFIRMATION_REVIEWED = "CONFIRMATION_REVIEWED"
    REFERRAL_SENT = "REFERRAL_SENT"
    REFERRAL_ACCEPTED = "REFERRAL_ACCEPTED"
    REFERRAL_REJECTED = "REFERRAL_REJECTED"
    OWNER_CHANGED = "OWNER_CHANGED"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    VISIT_RECORDED = "VISIT_RECORDED"
    PLAN_CHECKIN = "PLAN_CHECKIN"
    PLAN_WEEK_LAPSED = "PLAN_WEEK_LAPSED"
    ESCALATED = "ESCALATED"
    UNREACHABLE_STEP = "UNREACHABLE_STEP"
    TASK_CREATED = "TASK_CREATED"
    ECONSULT_ASKED = "ECONSULT_ASKED"
    ECONSULT_ANSWERED = "ECONSULT_ANSWERED"
    CONSENT_CHANGED = "CONSENT_CHANGED"
    CASE_CLOSED = "CASE_CLOSED"
    CASE_REOPENED = "CASE_REOPENED"


class PlanSize(StrEnum):
    FULL = "full"
    SMALLER = "smaller"
    SMALLEST = "smallest"


class PlanActionKey(StrEnum):
    SALT = "salt"
    ACTIVITY = "activity"
    SLEEP = "sleep"
    HOME_BP_CHECK = "home_bp_check"


class CheckinStatus(StrEnum):
    DONE = "done"
    PARTLY = "partly"
    MISSED = "missed"


class EffectKind(StrEnum):
    ESCALATE_LEVEL_1 = "ESCALATE_LEVEL_1"
    ESCALATE_LEVEL_2 = "ESCALATE_LEVEL_2"
    ESCALATE_URGENT_REVIEW = "ESCALATE_URGENT_REVIEW"
    UNREACHABLE_REMINDER = "UNREACHABLE_REMINDER"
    UNREACHABLE_SECOND_CHANNEL = "UNREACHABLE_SECOND_CHANNEL"
    UNREACHABLE_CALL_TASK = "UNREACHABLE_CALL_TASK"
    UNREACHABLE_CLINICIAN_DECISION = "UNREACHABLE_CLINICIAN_DECISION"


@dataclass(frozen=True)
class ReadingData:
    systolic: int
    diastolic: int
    taken_at: datetime
    source: ReadingSource


@dataclass(frozen=True)
class CaseData:
    """Everything the engine needs to know about a case. Built by the API from rows."""

    state: State
    severity: Severity
    urgent: bool
    urgent_started_at: datetime | None
    urgent_review_done: bool
    urgent_review_escalated: bool
    step_started_at: datetime
    owner_user_id: int | None
    referral_status: ReferralStatus | None
    referral_to_user_id: int | None
    appointment_at: datetime | None
    confirmation_method: ConfirmationMethod | None
    confirmation_status: ConfirmationStatus | None
    not_confirmed_reviewed: bool
    closure_ready: bool
    share_consent_granted: bool
    escalation_level: int
    unreachable_stage: int
    needs_clinician_decision: bool
