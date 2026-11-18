"""Closure gate: the only way a case reaches CLOSED.

Rejects every role except clinician, and any closure without an evidence type plus
either an evidence reference or a decision note of the configured minimum length.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config as cfg
from .types import ClosureEvidence, Role


@dataclass(frozen=True)
class Verdict:
    ok: bool
    status: int = 200
    code: str = ""
    message: str = ""


OK = Verdict(True)


def validate_closure(role: Role, evidence_type: str | None, evidence_ref: str | None, decision_note: str | None) -> Verdict:
    if role != Role.CLINICIAN:
        return Verdict(False, 403, "FORBIDDEN_ROLE", "Only a clinician can close a case.")
    if not evidence_type or evidence_type not in {e.value for e in ClosureEvidence}:
        return Verdict(False, 422, "CLOSURE_EVIDENCE_TYPE_REQUIRED", "Closing a case needs an evidence type from the list.")
    ref = (evidence_ref or "").strip()
    note = (decision_note or "").strip()
    min_chars = int(cfg.value("closure", "note_min_chars"))
    if not ref and len(note) < min_chars:
        return Verdict(
            False,
            422,
            "CLOSURE_EVIDENCE_REQUIRED",
            f"Closing a case needs an evidence reference or a decision note of at least {min_chars} characters.",
        )
    return OK


def validate_reopen(role: Role, reason: str | None) -> Verdict:
    if role != Role.CLINICIAN:
        return Verdict(False, 403, "FORBIDDEN_ROLE", "Only a clinician can reopen a case.")
    min_chars = int(cfg.value("closure", "reopen_reason_min_chars"))
    if len((reason or "").strip()) < min_chars:
        return Verdict(False, 422, "REOPEN_REASON_REQUIRED", f"Reopening needs a reason of at least {min_chars} characters.")
    return OK
