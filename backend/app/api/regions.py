"""Region configuration: languages and emergency advice. Text only; never read by routing."""

from __future__ import annotations

REGIONS = {
    "AUH": {
        "name": "Abu Dhabi",
        "default_language": "ar",
        "languages": ["ar", "en"],
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
        "emergency_number": None,
        "emergency_text": {
            "en": "Go to the nearest emergency department now.",
            "ar": "توجه الآن إلى أقرب قسم طوارئ.",
            "fr": "Rendez-vous maintenant au service des urgences le plus proche.",
        },
    },
}


def emergency_text(region: str, language: str) -> str:
    texts = REGIONS[region]["emergency_text"]
    return texts.get(language) or texts["en"]
