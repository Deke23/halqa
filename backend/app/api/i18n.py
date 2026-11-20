"""Display text in en, ar and fr for what the server supplies: people, places, labels and error messages.

Data lives in `i18n_data/names.yaml` (people, places, labels) and `i18n_data/messages.yaml` (one catalogue of error messages
per code and language). Config labels and template purposes are in `engine/config.yaml` and the template files themselves.
Unknown values fall back to the stored text in every language, never to a made-up translation.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

LANGS = ("en", "ar", "fr")
DEFAULT_LANG = "en"
_DATA = Path(__file__).with_name("i18n_data")
_BRACKETED = re.compile(r"^(.*?)\s*\((.*)\)\s*$")


@lru_cache(maxsize=1)
def _names() -> dict[str, Any]:
    return yaml.safe_load((_DATA / "names.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _messages() -> dict[str, Any]:
    raw = yaml.safe_load((_DATA / "messages.yaml").read_text(encoding="utf-8"))
    entries = []
    for e in raw["messages"]:
        pattern = re.sub(r"\\\{(\w+)\\\}", lambda m: f"(?P<{m.group(1)}>.+?)", re.escape(e["en"]))
        entries.append({**e, "regex": re.compile(pattern, re.S)})
    return {"entries": entries, "terms": raw["terms"]}


def same(text: str) -> dict[str, str]:
    return {lang: text for lang in LANGS}


def tri(d: dict[str, str] | None, fallback: str = "") -> dict[str, str]:
    d = d or {}
    return {lang: d.get(lang) or d.get("en") or fallback for lang in LANGS}


# ---------------------------------------------------------------- people


def _split(full: str) -> tuple[str, str | None]:
    m = _BRACKETED.match(full)
    return (m.group(1), m.group(2)) if m else (full, None)


def person_names(full: str) -> dict[str, str]:
    """The name in en, ar and fr, with no role in brackets. Patient names are a first name plus an initial."""
    staff = _names()["staff"].get(full)
    if staff:
        return tri(staff["name"])
    base, _ = _split(full)
    parts = base.split()
    first = _names()["first_names"].get(parts[0]) if parts else None
    if not first:
        return same(base)
    letters = _names()["initials_ar"]
    ar = " ".join([first["ar"]] + [letters.get(p.rstrip(".").upper(), p) + ("." if p.endswith(".") else "") for p in parts[1:]])
    return {"en": base, "ar": ar, "fr": base}


def person_roles(full: str, fallback_role: str = "") -> dict[str, str]:
    """The job title in en, ar and fr: the bracketed text, or the access role when the name has none."""
    staff = _names()["staff"].get(full)
    if staff:
        return tri(staff["role"])
    _, role = _split(full)
    if role:
        return same(role)
    return tri(_names()["roles"].get(fallback_role), fallback_role)


def initials_i18n(full: str) -> dict[str, str]:
    """Initials per language: Latin for en and fr, Arabic letters for ar. Built from the first name and the surname initial."""
    base = person_names(full)
    out = {}
    for lang in LANGS:
        words = [w for w in re.split(r"[\s\-]+", base[lang]) if w]
        out[lang] = "".join(w[0] for w in words[:2]).upper() if lang != "ar" else "".join(w[0] for w in words[:2])
    return out


def place(name: str) -> dict[str, str]:
    return tri(_names()["places"].get(name), name)


def region_names(code: str) -> dict[str, str]:
    return tri(_names()["regions"].get(code), code)


def service(key: str | None) -> dict[str, str] | None:
    return tri(_names()["services"].get(key), key or "") if key else None


def task_title(title_key: str) -> dict[str, str]:
    return tri(_names()["task_titles"].get(title_key), title_key)


def closure_label(code: str) -> dict[str, str]:
    return tri(_names()["closure_evidence"].get(code), code)


def simulated_label() -> dict[str, str]:
    return tri(_names()["simulated_label"])


def all_people_label() -> dict[str, str]:
    return tri(_names()["all_people"])


def config_notice() -> dict[str, str]:
    return tri(_names()["notice"])


def config_rules() -> list[dict[str, str]]:
    return [tri(r) for r in _names()["rules"]]


def cover_label(kind: str, **params: Any) -> dict[str, str]:
    base = tri(_names()["cover"][kind])
    return {lang: text.format(**params) for lang, text in base.items()}


# ---------------------------------------------------------------- error messages


def pick_language(header: str | None) -> str:
    """The first supported language in an Accept-Language header, honouring q values; default en."""
    if not header:
        return DEFAULT_LANG
    ranked = []
    for i, part in enumerate(header.split(",")):
        tag, _, q = part.strip().partition(";q=")
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 0.0
        code = tag.strip().lower().split("-")[0]
        if code in LANGS and weight > 0:
            ranked.append((-weight, i, code))
    return min(ranked)[2] if ranked else DEFAULT_LANG


def _term(kind: str, value: str, lang: str) -> str:
    entry = _messages()["terms"].get(kind, {}).get(value)
    return (entry or {}).get(lang) or value


def translate_error(code: str, message: str, lang: str) -> str:
    """The error message in `lang`. English is the text the code produced; unknown messages stay as they are."""
    if lang == "en":
        return message
    for e in _messages()["entries"]:
        if e["code"] != code:
            continue
        m = e["regex"].fullmatch(message)
        if not m:
            continue
        params = m.groupdict()
        for key, kind in (("state", "states"), ("action", "actions"), ("source", "sources")):
            if key in params:
                params[key] = _term(kind, params[key], lang)
        if "role" in params:
            params["role"] = tri(_names()["roles"].get(params["role"]), params["role"])[lang]
        try:
            return e[lang].format(**params)
        except (KeyError, IndexError):
            return message
    return message


def catalogue() -> list[dict[str, Any]]:
    """Every catalogued message (code and the three texts), for tests and documentation."""
    return [{k: v for k, v in e.items() if k != "regex"} for e in _messages()["entries"]]
