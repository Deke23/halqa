"""Optional AI re-wording with validation and template fallback. Never raises to the caller."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import providers
from .validator import validate


@dataclass(frozen=True)
class Reworded:
    text: str
    source: str  # "TEMPLATE" or "AI_REWORDED"
    validation: dict = field(default_factory=dict)


def reword(text: str, language: str, tone: str | None = None, slots: dict | None = None,
           *, max_length: int | None = None) -> Reworded:
    """Return AI re-worded text only if every validator check passes; otherwise the original text.

    `max_length` is the channel limit (for example 160 for SMS). Provider comes from env WORDING_PROVIDER.
    """
    provider = (os.environ.get("WORDING_PROVIDER") or "none").strip().lower()
    if provider == "none":
        return Reworded(text=text, source="TEMPLATE",
                        validation={"passed": True, "failed_reason": None, "checks": [], "provider": "none"})
    try:
        candidate = providers.call_provider(provider, providers.system_prompt(language, tone), text).strip()
        result = validate(text, candidate, language, slots or {}, max_length)
        result["provider"] = provider
        if result["passed"]:
            return Reworded(text=candidate, source="AI_REWORDED", validation=result)
        return Reworded(text=text, source="TEMPLATE", validation=result)
    except Exception as exc:  # timeout, HTTP error, bad JSON, missing key: all fall back to the template
        return Reworded(text=text, source="TEMPLATE",
                        validation={"passed": False, "failed_reason": f"provider_error: {type(exc).__name__}",
                                    "checks": [], "provider": provider})
