"""Action table: which role may do what, in which state.

`check` answers with a verdict carrying the HTTP status the API should return:
403 wrong role, 409 state or rule does not allow it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .closure import OK, Verdict
from .types import OPEN_STATES, Action, CaseData, ReferralStatus, Role, State

R = Role


@dataclass(frozen=True)
class Rule:
    roles: frozenset[Role]
    states: frozenset[State]


def _rule(roles: set[Role], states: set[State] | frozenset[State]) -> Rule:
    return Rule(frozenset(roles), frozenset(states))


ACTION_TABLE: dict[Action, Rule] = {
    Action.NOTIFY: _rule({R.COORDINATOR, R.SYSTEM}, {State.RESULT_ISSUED}),
    Action.ACKNOWLEDGE: _rule({R.PATIENT}, {State.NOTIFIED}),
    Action.CHOOSE_CONFIRMATION: _rule({R.PATIENT, R.COORDINATOR}, {State.ACKNOWLEDGED}),
    Action.ADD_READING: _rule({R.PATIENT, R.COORDINATOR, R.CLINICIAN}, OPEN_STATES),
    Action.REVIEW_CONFIRMATION: _rule({R.CLINICIAN}, {State.ACKNOWLEDGED}),
    Action.REFER: _rule({R.CLINICIAN}, {State.CONFIRMED}),
    Action.ACCEPT_REFERRAL: _rule({R.CLINICIAN}, {State.REFERRED}),
    Action.REJECT_REFERRAL: _rule({R.CLINICIAN}, {State.REFERRED}),
    Action.ASSIGN_OWNER: _rule({R.COORDINATOR}, OPEN_STATES),
    Action.BOOK_APPOINTMENT: _rule({R.PATIENT, R.COORDINATOR}, {State.REFERRED}),
    Action.RECORD_VISIT: _rule({R.CLINICIAN}, {State.APPOINTMENT_BOOKED}),
    Action.PLAN_CHECKIN: _rule({R.PATIENT}, {State.IN_CARE}),
    Action.ESCALATE: _rule({R.COORDINATOR, R.CLINICIAN}, OPEN_STATES),
    Action.CLOSE: _rule({R.CLINICIAN}, OPEN_STATES),
    Action.REOPEN: _rule({R.CLINICIAN}, {State.CLOSED}),
    Action.UPDATE_CONSENT: _rule({R.PATIENT}, set(State)),
    Action.COMPLETE_URGENT_REVIEW: _rule({R.CLINICIAN}, OPEN_STATES),
}


def _urgent_pending(case: CaseData) -> bool:
    return case.urgent and not case.urgent_review_done


def check(action: Action, role: Role, case: CaseData, user_id: int | None = None) -> Verdict:
    """Role first (403), then state and rule preconditions (409)."""
    rule = ACTION_TABLE[action]
    if role not in rule.roles:
        return Verdict(False, 403, "FORBIDDEN_ROLE", f"The {role.value} role may not perform {action.value}.")
    if case.state not in rule.states:
        return Verdict(False, 409, "WRONG_STATE", f"{action.value} is not possible while the case is {case.state.value}.")

    if action == Action.COMPLETE_URGENT_REVIEW and not _urgent_pending(case):
        return Verdict(False, 409, "NO_URGENT_REVIEW", "There is no urgent review waiting for this case.")
    if action == Action.REFER:
        if case.referral_status in (ReferralStatus.PENDING, ReferralStatus.ACCEPTED):
            return Verdict(False, 409, "REFERRAL_ACTIVE", "This case already has an active referral.")
        if not case.share_consent_granted:
            return Verdict(
                False,
                409,
                "CONSENT_WITHDRAWN",
                "The patient has withdrawn permission to share with the receiving provider. Ask the patient before referring.",
            )
    if action in (Action.ACCEPT_REFERRAL, Action.REJECT_REFERRAL):
        if case.referral_status != ReferralStatus.PENDING:
            return Verdict(False, 409, "NO_PENDING_REFERRAL", "There is no pending referral to decide.")
        if user_id is not None and case.referral_to_user_id is not None and user_id != case.referral_to_user_id:
            return Verdict(False, 403, "NOT_RECEIVING_CLINICIAN", "Only the receiving clinician can decide this referral.")
    if action == Action.BOOK_APPOINTMENT and case.referral_status != ReferralStatus.ACCEPTED:
        return Verdict(False, 409, "REFERRAL_NOT_ACCEPTED", "An appointment can be booked after the receiving clinician accepts the referral.")
    return OK


def allowed_actions(case: CaseData, role: Role, user_id: int | None = None) -> list[Action]:
    return [a for a in Action if check(a, role, case, user_id).ok]
