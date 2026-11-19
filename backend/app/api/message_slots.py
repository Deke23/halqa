"""Slot values for message templates: stored language-neutral, formatted at render time.

A message stores *neutral* slots: names, readings and ISO timestamps in UTC. `localize` turns them into the strings a
template needs, for one language and one region time zone. Because the neutral values are stored with the message, a
re-render in another language never drifts: the due date and the reading are the ones from the moment it was created.

Clinical values and clock times keep Latin digits in every language. Month names follow the message language.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from . import wording_port
from .regions import emergency_text, tz_of

# Templates that quote the reading that opened the case, not the latest home reading.
INDEX_READING_TEMPLATES = frozenset({"result_raised", "result_severe", "teach_back_question", "teach_back_simpler",
                                     "teach_back_question_app"})

_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
           "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
}


def base_template_id(template_id: str) -> str:
    """The template without its channel suffix (`_sms`, `_app`)."""
    for suffix in ("_sms", "_app"):
        if template_id.endswith(suffix):
            return template_id[: -len(suffix)]
    return template_id


def to_iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def _local(value: str | datetime | None, region: str) -> datetime | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    return moment.astimezone(tz_of(region))


def format_date(moment: datetime, language: str) -> str:
    """Day number in Latin digits and the month name in the message language, for example `22 November` or `22 نوفمبر`."""
    months = _MONTHS.get(language, _MONTHS["en"])
    return f"{moment.day} {months[moment.month - 1]}"


def localize(neutral: dict[str, Any], language: str, region: str) -> dict[str, Any]:
    """Template slots for one language, with dates and times on the region's local clock."""
    due = _local(neutral.get("due_at"), region)
    review = _local(neutral.get("review_at"), region)
    appt = _local(neutral.get("appointment_at"), region)
    closed = _local(neutral.get("closed_at"), region)
    plan = neutral.get("plan") or {}
    action = wording_port.plan_text(plan["action_key"], plan["size"], language) if plan else ""
    slots = {
        "name": neutral.get("name", ""), "patient_name": neutral.get("name", ""),
        "systolic": neutral.get("systolic", ""), "diastolic": neutral.get("diastolic", ""), "reading": neutral.get("reading", ""),
        "phone": neutral.get("phone", ""), "clinic": neutral.get("clinic", ""), "clinic_name": neutral.get("clinic", ""),
        "provider": neutral.get("provider", ""),
        "due_date": format_date(due, language) if due else "",
        "review_time": review.strftime("%H:%M") if review else "",
        "date": appt.strftime("%Y-%m-%d") if appt else "", "time": appt.strftime("%H:%M") if appt else "",
        "appointment_date": format_date(appt, language) if appt else "",
        "appointment_time": appt.strftime("%H:%M") if appt else "",
        "action": action, "action_text": action, "closure_reason": neutral.get("closure_reason", ""),
        "emergency_instruction": emergency_text(region, language),
        "closed_date": format_date(closed, language) if closed else "",
    }
    return slots
