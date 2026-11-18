"""The only door from the API to the wording module.

Safety property: wording output is text only. Nothing in this file feeds routing, urgency,
ownership, SLA or closure. If `app.wording` is missing, disabled or lacks a template, a
built-in plain English string is used, and the engine behaves identically.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

FALLBACK_VERSION = "builtin-1"

_FALLBACK: dict[str, str] = {
    "result_raised": (
        "Your blood pressure reading was {reading}. This is a raised reading that needs checking. "
        "It is not a diagnosis. We will help you check it again."
    ),
    "result_severe": (
        "Your blood pressure reading was {reading}, which is much higher than usual. A clinician will review it today. "
        "If you have chest pain, shortness of breath, a severe headache, a change in vision, confusion or weakness on one side, "
        "get emergency help now."
    ),
    "teach_back_question": (
        "What is the next step? Reply 1 if you understand that you need to check your blood pressure again, or 2 if you would like a call."
    ),
    "teach_back_simpler": (
        "One high reading is not enough to know what is happening. The next step is to measure again, at home or at a clinic. "
        "Reply 1 if this is clear, or 2 if you would like a call."
    ),
    "reminder_ack": "A reminder: your blood pressure reading {reading} still needs checking. Reply 1 if you understand, or 2 for a call.",
    "confirmation_hbpm_instructions": (
        "Measure your blood pressure twice a day, morning and evening, for at least 4 days. Sit quietly for 5 minutes first. "
        "Enter each result in the app, or reply with it, for example 150/95."
    ),
    "confirmation_abpm_booking": "A 24-hour blood pressure monitor visit will be arranged for you. We will send the time.",
    "referral_sent": "Your clinician has sent you to a specialist team for a closer look. We will tell you when they reply.",
    "referral_accepted": "The specialist team accepted your referral. You can now choose a visit time.",
    "appointment_booked": "Your visit is booked for {date} at {time}, {clinic}.",
    "appointment_reminder": "A reminder: your visit is on {date} at {time}, {clinic}.",
    "weekly_action": "Your action for this week: {action}",
    "no_blame_checkin": "It is fine that last week did not go to plan. Weeks like that happen. We will make this week easier.",
    "plan_smaller": "This week's action is smaller: {action}",
    "case_closed_summary": "Your follow-up is complete. Your clinician recorded the reason: {closure_reason}.",
    "urgent_red_flags": (
        "Get emergency help now if you have chest pain, shortness of breath, a severe headache, a change in vision, "
        "confusion or weakness on one side."
    ),
    "reply_received": "Thank you. We received your reply.",
    "call_requested": "Thank you. A member of the care team will call you.",
    "reply_not_understood": "We could not read that reply. Reply 1 if you understand, or 2 if you would like a call.",
}

PLAN_TEXT: dict[tuple[str, str], str] = {
    ("salt", "full"): "Leave the salt shaker off the table at every meal this week.",
    ("salt", "smaller"): "Leave the salt shaker off the table at one meal a day this week.",
    ("salt", "smallest"): "Taste your food before adding salt, once this week.",
    ("activity", "full"): "Walk for 30 minutes on five days this week.",
    ("activity", "smaller"): "Walk for 15 minutes on three days this week.",
    ("activity", "smallest"): "Take a 10-minute walk once this week.",
    ("sleep", "full"): "Go to bed at the same time every night this week.",
    ("sleep", "smaller"): "Go to bed at the same time on three nights this week.",
    ("sleep", "smallest"): "Choose one night this week and go to bed 30 minutes earlier.",
    ("home_bp_check", "full"): "Check your blood pressure at home every morning this week.",
    ("home_bp_check", "smaller"): "Check your blood pressure at home on three mornings this week.",
    ("home_bp_check", "smallest"): "Check your blood pressure at home once this week.",
}


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return ""


@dataclass
class Rendered:
    text: str
    template_id: str
    template_version: str
    language: str
    source: str = "TEMPLATE"
    validation: dict[str, Any] = field(default_factory=dict)


def _wording() -> Any | None:
    try:
        return importlib.import_module("app.wording")
    except Exception as exc:  # module missing or broken: use the built-in text
        log.debug("wording module unavailable: %s", exc)
        return None


_FIXED = {  # fixed replies for the phone thread when no approved template exists
    "reply_received": {"en": "Thank you. We received your reply.", "fr": "Merci. Nous avons bien reçu votre réponse.",
                       "ar": "شكراً. استلمنا ردك."},
    "call_requested": {"en": "Thank you. A member of the care team will call you.",
                       "fr": "Merci. Un membre de l'équipe de soins vous appellera.",
                       "ar": "شكراً. سيتصل بك أحد أعضاء فريق الرعاية."},
    "reply_not_understood": {"en": "Sorry, please reply with 1 if you understand, 2 for a call, or a reading such as 150/95.",
                             "fr": "Désolé, répondez 1 si vous avez compris, 2 pour un appel, ou une mesure comme 150/95.",
                             "ar": "معذرة، أرسل 1 إذا فهمت، أو 2 للاتصال، أو قراءة مثل 150/95."},
}

_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
           "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
}


def format_date(dt, language: str) -> str:
    """Localised month name, Latin digits for the day (clinical and scheduling numbers stay Latin)."""
    months = _MONTHS.get(language, _MONTHS["en"])
    return f"{dt.day} {months[dt.month - 1]}"


def _catalogue_ids(mod: Any) -> set[str]:
    try:
        return {t["id"] for t in mod.list_templates()}
    except Exception:
        return set()


def render(template_id: str, language: str, slots: dict[str, Any], channel: str | None = None) -> Rendered:
    """Approved template text. SMS uses the `_sms` variant when one exists."""
    mod = _wording()
    if mod is not None and hasattr(mod, "render"):
        tid = template_id
        if channel == "SMS" and not tid.endswith("_sms") and f"{tid}_sms" in _catalogue_ids(mod):
            tid = f"{tid}_sms"
        try:
            out = mod.render(tid, language, slots)
            return Rendered(out.text, out.template_id, str(out.template_version), out.language)
        except Exception as exc:
            log.debug("wording.render failed for %s: %s", tid, exc)
    if template_id in _FIXED:
        return Rendered(_FIXED[template_id].get(language, _FIXED[template_id]["en"]), template_id, FALLBACK_VERSION, language)
    text = _FALLBACK.get(template_id, "")
    return Rendered(text.format_map(_Blank(slots)), template_id, FALLBACK_VERSION, "en")


def teach_back(language: str, slots: dict[str, Any], sms: bool = False) -> dict[str, Any]:
    """Question, options, correct option number and simpler text. Built-in English if the module is missing."""
    mod = _wording()
    if mod is not None and hasattr(mod, "teach_back"):
        try:
            return dict(mod.teach_back(language, slots, sms=sms))
        except Exception as exc:
            log.debug("wording.teach_back failed: %s", exc)
    return {
        "question": _FALLBACK["teach_back_question"], "correct": 2, "simpler": _FALLBACK["teach_back_simpler"],
        "options": ["Nothing, the reading is normal", "Check my blood pressure again", "Start medicine now"],
    }


def reword(text: str, language: str, tone: str | None, slots: dict[str, Any], base: Rendered, max_length: int | None = None) -> Rendered:
    """Optional AI re-wording. Any failure returns the template text unchanged."""
    mod = _wording()
    if mod is None or not hasattr(mod, "reword"):
        return base
    try:
        out = mod.reword(text, language, tone, slots, max_length=max_length)
    except Exception as exc:
        log.debug("wording.reword failed: %s", exc)
        return base
    validation = dict(getattr(out, "validation", {}) or {})
    if out.source != "AI_REWORDED":
        return Rendered(base.text, base.template_id, base.template_version, base.language, "TEMPLATE", validation)
    return Rendered(out.text, base.template_id, base.template_version, base.language, "AI_REWORDED", validation)


def plan_text(action_key: str, size: str) -> str:
    return PLAN_TEXT.get((action_key, size), "")


def template_catalogue() -> list[dict[str, Any]]:
    mod = _wording()
    if mod is not None and hasattr(mod, "list_templates"):
        try:
            return list(mod.list_templates())
        except Exception as exc:
            log.debug("wording.list_templates failed: %s", exc)
    return [{"id": k, "version": FALLBACK_VERSION, "languages": ["en"]} for k in sorted(_FALLBACK)]
