"""The state machine as data.

Safety property: the only entry that can produce CLOSED is the `close` action, which is
guarded by the closure gate. No timer, job or rule has a path to CLOSED.
"""

from __future__ import annotations

from .types import Action, State

# Sentinel target: reopen returns the case to the state it was in when it was closed.
PREVIOUS = "PREVIOUS"

OPEN = [s for s in State if s is not State.CLOSED]

TRANSITIONS: dict[Action, dict[State, State | str]] = {
    Action.NOTIFY: {State.RESULT_ISSUED: State.NOTIFIED},
    Action.ACKNOWLEDGE: {State.NOTIFIED: State.ACKNOWLEDGED},
    # CONFIRMED outcome only. NOT_CONFIRMED keeps the case in ACKNOWLEDGED.
    Action.REVIEW_CONFIRMATION: {State.ACKNOWLEDGED: State.CONFIRMED},
    Action.REFER: {State.CONFIRMED: State.REFERRED},
    Action.REJECT_REFERRAL: {State.REFERRED: State.CONFIRMED},
    Action.BOOK_APPOINTMENT: {State.REFERRED: State.APPOINTMENT_BOOKED},
    Action.RECORD_VISIT: {State.APPOINTMENT_BOOKED: State.IN_CARE},
    Action.CLOSE: {s: State.CLOSED for s in OPEN},
    Action.REOPEN: {State.CLOSED: PREVIOUS},
}


def target_state(action: Action, current: State) -> State | str | None:
    """The state this action leads to from `current`, or None when it does not change state."""
    return TRANSITIONS.get(action, {}).get(current)


def producers_of_closed() -> set[Action]:
    """Actions whose transition table can produce CLOSED. Must always be exactly {close}."""
    return {a for a, table in TRANSITIONS.items() if State.CLOSED in table.values()}
