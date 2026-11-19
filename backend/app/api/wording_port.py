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
        "What is the next step? A) Nothing, the reading is normal. B) Check my blood pressure again. C) Start medicine now. Reply A, B or C."
    ),
    "teach_back_simpler": (
        "One high reading is not enough to know what is happening. The next step is to measure again, at home or at a clinic. "
        "Please try the question again."
    ),
    "reminder_ack": "A reminder: your blood pressure reading {reading} still needs checking. Reply 0 for a call.",
    "reminder_home_readings": "A reminder: your follow-up blood pressure check is not finished yet. Please send your readings by {due_date}. If you need help, tell us.",
    "reminder_booking": "A reminder: you can now choose a visit time. Please choose one by {due_date}. If you need help, tell us.",
    "appointment_reminder": "A reminder: your visit is on {appointment_date} at {appointment_time}, {clinic_name}.",
    "red_flag_check": "Do you have chest pain, trouble breathing, a severe headache, a change in vision, confusion or weakness on one side now? Reply 1 for yes, 2 for no, or 0 for a call.",
    "urgent_red_flags_sms": "{emergency_instruction}",
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
    "reply_not_understood": "We could not read that reply. Reply 0 if you would like a call.",
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
    "stop_confirmed": {"en": "You will not get more messages on this number. Your care team will reach you another way you have agreed to.",
                       "fr": "Vous ne recevrez plus de messages sur ce numéro. L'équipe de soins vous contactera d'une autre façon que vous avez acceptée.",
                       "ar": "لن تصلك رسائل أخرى على هذا الرقم. سيتواصل معك فريق الرعاية بطريقة أخرى سبق أن وافقت عليها."},
    "reply_not_understood": {"en": "Sorry, we could not read that. Please use one of the replies we offered, or reply 0 for a call.",
                             "fr": "Désolé, nous n'avons pas compris. Utilisez l'une des réponses proposées, ou répondez 0 pour un appel.",
                             "ar": "معذرة، لم نفهم ردك. استخدم أحد الردود المقترحة، أو أرسل 0 لمكالمة."},
}

def _catalogue_ids(mod: Any) -> set[str]:
    try:
        return {t["id"] for t in mod.list_templates()}
    except Exception:
        return set()


class WordingUnavailable(Exception):
    """Raised by `render(..., strict=True)` when the approved template cannot be rendered."""


def _channel_variant(template_id: str, channel: str | None, ids: set[str]) -> str:
    """SMS uses the `_sms` variant and the in-app thread uses the `_app` variant when one exists."""
    suffix = {"SMS": "_sms", "APP": "_app"}.get(channel or "")
    if suffix and not template_id.endswith(("_sms", "_app")) and f"{template_id}{suffix}" in ids:
        return f"{template_id}{suffix}"
    return template_id


def known_template(template_id: str) -> bool:
    mod = _wording()
    if mod is not None and hasattr(mod, "list_templates"):
        return template_id in _catalogue_ids(mod)
    return template_id in _FALLBACK


def render(template_id: str, language: str, slots: dict[str, Any], channel: str | None = None, *, strict: bool = False) -> Rendered:
    """Approved template text, deterministic. With `strict`, a template that cannot render raises WordingUnavailable."""
    mod = _wording()
    if mod is not None and hasattr(mod, "render"):
        tid = _channel_variant(template_id, channel, _catalogue_ids(mod))
        try:
            out = mod.render(tid, language, slots)
            return Rendered(out.text, out.template_id, str(out.template_version), out.language)
        except Exception as exc:
            log.debug("wording.render failed for %s: %s", tid, exc)
            if strict:
                raise WordingUnavailable(f"{tid} in {language}: {exc}") from exc
    if template_id in _FIXED:
        return Rendered(_FIXED[template_id].get(language, _FIXED[template_id]["en"]), template_id, FALLBACK_VERSION, language)
    text = _FALLBACK.get(template_id, "")
    if strict and not text:
        raise WordingUnavailable(f"No text for {template_id}")
    return Rendered(text.format_map(_Blank(slots)), template_id, FALLBACK_VERSION, "en")


def teach_back(language: str, slots: dict[str, Any], sms: bool = False, app: bool = False) -> dict[str, Any]:
    """Question, options, correct option number and simpler text. Built-in English if the module is missing.

    `app=True` gives the in-app question without the "reply 1, 2 or 3" sentence (that belongs to the SMS variant only).
    """
    mod = _wording()
    if mod is not None and hasattr(mod, "teach_back"):
        try:
            return dict(mod.teach_back(language, slots, sms=sms, app=app))
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


def plan_text(action_key: str, size: str, language: str = "en") -> str:
    """Weekly action text from the approved templates (`plan_action_<key>_<size>`), in the given language."""
    try:
        return render(f"plan_action_{action_key}_{size}", language, {}, strict=True).text
    except WordingUnavailable:
        return PLAN_TEXT.get((action_key, size), "")


def validate_text(original: str, candidate: str, language: str, slots: dict[str, Any], max_length: int | None) -> dict[str, Any]:
    """Re-run the wording validator. Raises WordingUnavailable when the validator cannot be reached."""
    mod = _wording()
    if mod is None or not hasattr(mod, "validate"):
        raise WordingUnavailable("The wording validator is not available.")
    return dict(mod.validate(original, candidate, language, slots, max_length))


def channel_limit(template_id: str, channel: str, language: str) -> int | None:
    """Channel character limit for a template (SMS limit by language, else the app or WhatsApp limit), if declared."""
    mod = _wording()
    if mod is None or not hasattr(mod, "get_template"):
        return None
    try:
        limits = mod.get_template(template_id)["channel_limits"]
    except Exception:
        return None
    if channel == "SMS":
        sms = limits.get("sms") if isinstance(limits, dict) else None
        return sms.get(language) if isinstance(sms, dict) else None
    key = "whatsapp" if channel == "WHATSAPP" else "app"
    value = limits.get(key) if isinstance(limits, dict) else None
    return int(value) if isinstance(value, int) else None


def template_catalogue() -> list[dict[str, Any]]:
    mod = _wording()
    if mod is not None and hasattr(mod, "list_templates"):
        try:
            return list(mod.list_templates())
        except Exception as exc:
            log.debug("wording.list_templates failed: %s", exc)
    return [{"id": k, "version": FALLBACK_VERSION, "languages": ["en"]} for k in sorted(_FALLBACK)]
