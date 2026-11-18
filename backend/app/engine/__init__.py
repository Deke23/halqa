"""Case engine: pure Python, no I/O, no database, no wording imports.

Every function that depends on time takes `now`. Thresholds and service levels come
only from config.yaml.
"""

from . import config, plan, queues, urgency
from .actions import ACTION_TABLE, allowed_actions, check
from .closure import Verdict, validate_closure, validate_reopen
from .sla import Effect, Evaluation, NextStep, evaluate, next_step
from .states import PREVIOUS, TRANSITIONS, producers_of_closed, target_state
from .types import *  # noqa: F401,F403
from .urgency import classify, evaluate_confirmation

__all__ = [
    "ACTION_TABLE", "PREVIOUS", "TRANSITIONS", "Effect", "Evaluation", "NextStep", "Verdict",
    "allowed_actions", "check", "classify", "config", "evaluate", "evaluate_confirmation", "next_step",
    "plan", "producers_of_closed", "queues", "target_state", "urgency", "validate_closure", "validate_reopen",
]
