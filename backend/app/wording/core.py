"""Template loading and deterministic rendering."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

LANGUAGES = ("en", "ar", "fr")
TEMPLATE_DIR = Path(__file__).parent / "templates"
_SLOT = re.compile(r"\{(\w+)\}")


class TemplateError(Exception):
    """Base class for wording errors raised by `render`."""


class UnknownTemplateError(TemplateError, KeyError):
    pass


class UnsupportedLanguageError(TemplateError, ValueError):
    pass


class MissingSlotError(TemplateError, KeyError):
    pass


@dataclass(frozen=True)
class Rendered:
    text: str
    template_id: str
    template_version: int
    language: str
    # Structured extras, for example teach-back options: {"options": [...], "correct": 2}
    extra: dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict]:
    templates = {}
    for path in sorted(TEMPLATE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        templates[data["id"]] = data
    return templates


def get_template(template_id: str) -> dict:
    try:
        return _load_all()[template_id]
    except KeyError:
        raise UnknownTemplateError(f"Unknown template id: {template_id!r}") from None


def _fill(text: str, slots: dict) -> str:
    return _SLOT.sub(lambda m: str(slots[m.group(1)]), text)


def render(template_id: str, language: str, slots: dict | None = None) -> Rendered:
    """Fill an approved template. Deterministic. Raises a TemplateError subclass on any problem."""
    tpl = get_template(template_id)
    if language not in LANGUAGES or language not in tpl["text"]:
        raise UnsupportedLanguageError(f"Language {language!r} is not available for template {template_id!r}")
    slots = slots or {}
    missing = [s for s in tpl["required_slots"] if s not in slots or slots[s] in (None, "")]
    if missing:
        raise MissingSlotError(f"Template {template_id!r} needs slot(s): {', '.join(missing)}")
    text = _fill(tpl["text"][language], slots)
    extra: dict[str, Any] = {}
    if "options" in tpl:
        extra["options"] = list(tpl["options"][language])
        extra["correct"] = tpl["correct"]
        if not template_id.endswith(("_sms", "_app")):  # SMS lists them inline; the app shows them as structured options; chat variants label them A, B, C
            text += "\n" + "\n".join(f"{chr(64 + i)}. {o}" for i, o in enumerate(extra["options"], 1))
    return Rendered(text=text, template_id=template_id, template_version=tpl["version"], language=language, extra=extra)


def teach_back(language: str, slots: dict, sms: bool = False, app: bool = False) -> dict:
    """Question text, options, correct option number and the simpler re-explanation, in one dict.

    `app=True` returns the in-app question, which has no "reply 1, 2 or 3" sentence (that belongs to the SMS variant only).
    """
    q = render("teach_back_question_sms" if sms else "teach_back_question_app" if app else "teach_back_question", language, slots)
    simpler = render("teach_back_simpler", language, slots)
    return {"question": q.text, "options": q.extra["options"], "correct": q.extra["correct"], "simpler": simpler.text}


def list_templates() -> list[dict]:
    """Catalogue for GET /api/config."""
    out = []
    for tid, tpl in sorted(_load_all().items()):
        out.append({
            "id": tid,
            "version": tpl["version"],
            "purpose": tpl["purpose"],
            "purpose_i18n": tpl.get("purpose_i18n") or {l: tpl["purpose"] for l in LANGUAGES},
            "languages": [l for l in LANGUAGES if l in tpl["text"]],
            "required_slots": list(tpl["required_slots"]),
            "channel_limits": tpl["channel_limits"],
        })
    return out
