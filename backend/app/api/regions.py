"""Region configuration: languages, time zone, emergency advice and opt-out words. Text and clock only; never read by routing."""

from __future__ import annotations

import unicodedata
from datetime import timedelta, timezone, tzinfo
from functools import lru_cache

REGIONS = {
    "AUH": {
        "name": "Abu Dhabi",
        "default_language": "ar",
        "languages": ["ar", "en"],
        "timezone": "Asia/Dubai",
        "emergency_number": "998",
        "emergency_text": {
            "en": "Call 998 now and ask for an ambulance.",
            "ar": "اتصل بالرقم 998 الآن واطلب الإسعاف.",
            "fr": "Appelez le 998 maintenant et demandez une ambulance.",
        },
    },
    "YDE": {
        "name": "Yaoundé",
        "default_language": "fr",
        "languages": ["fr", "en"],
        "timezone": "Africa/Douala",
        "emergency_number": None,
        "emergency_text": {
            "en": "Go to the nearest emergency department now.",
            "ar": "توجه الآن إلى أقرب قسم طوارئ.",
            "fr": "Rendez-vous maintenant au service des urgences le plus proche.",
        },
    },
}

# Used only if the system has no time zone database. Neither zone observes daylight saving time.
_FIXED_OFFSET_HOURS = {"Asia/Dubai": 4, "Africa/Douala": 1}


def emergency_text(region: str, language: str) -> str:
    texts = REGIONS[region]["emergency_text"]
    return texts.get(language) or texts["en"]


@lru_cache(maxsize=None)
def tz_of(region: str) -> tzinfo:
    """The region's local time zone (IANA name from config)."""
    name = REGIONS[region]["timezone"]
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # no tz database installed
        return timezone(timedelta(hours=_FIXED_OFFSET_HOURS[name]), name)


# ---------------------------------------------------------------- opt-out words (SMS reply STOP and equivalents)

STOP_KEYWORDS = {
    "en": ["STOP", "UNSUBSCRIBE", "QUIT", "CANCEL"],
    "fr": ["STOP", "ARRET", "ARRETER", "ARRETEZ", "DESABONNER", "ANNULER"],
    "ar": ["توقف", "ايقاف", "قف", "الغاء", "إلغاء", "إيقاف"],
}


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.strip())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return plain.strip(" .!").upper()


_STOP_SET = {_norm(w) for words in STOP_KEYWORDS.values() for w in words}


def is_stop_keyword(text: str) -> bool:
    """True when the whole reply is one of the configured opt-out words in any supported language."""
    return _norm(text) in _STOP_SET
