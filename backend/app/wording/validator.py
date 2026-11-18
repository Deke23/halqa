"""Validation of re-worded text. Pure functions, no I/O apart from reading the block list once.

`validate(original, candidate, language, slots, max_length)` returns:
    {"passed": bool, "failed_reason": str | None, "checks": [{"name", "passed", "detail"}]}
All checks always run so a reviewer can see every result, not only the first failure.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

BLOCKED_PATH = Path(__file__).parent / "blocked_words.yaml"
_DIGITS = re.compile(r"\d+")  # \d also matches Arabic-Indic digits, which counts as a change from Latin digits
_ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
_WORDS = re.compile(r"[A-Za-zÀ-ɏ']+")

# Tiny stopword lists, only to tell English from French when both are Latin script.
_STOP = {
    "en": {"the", "and", "you", "your", "is", "are", "to", "of", "this", "that", "with", "for", "it", "not", "we"},
    "fr": {"le", "la", "les", "et", "vous", "votre", "est", "sont", "de", "des", "du", "ce", "que", "pas", "nous", "un", "une"},
}


@lru_cache(maxsize=1)
def blocked_words() -> dict[str, list[str]]:
    data = yaml.safe_load(BLOCKED_PATH.read_text(encoding="utf-8"))
    return {lang: [w for group in groups.values() for w in group] for lang, groups in data.items()}


def find_blocked(text: str, language: str) -> list[str]:
    hits = []
    for word in blocked_words().get(language, []):
        if language == "ar":
            if word in text:
                hits.append(word)
        elif re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, flags=re.IGNORECASE):
            hits.append(word)
    return hits


def _slot_values(slots: dict) -> list[str]:
    return [str(v) for v in (slots or {}).values() if isinstance(v, (str, int, float)) and str(v).strip()]


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "passed": passed, "detail": detail}


def validate(original: str, candidate: str, language: str, slots: dict | None = None, max_length: int | None = None) -> dict:
    slots = slots or {}
    checks = []

    # 1. not empty
    candidate = candidate or ""
    checks.append(_check("not_empty", bool(candidate.strip())))

    # 2. every slot value used in the approved text is present, unchanged, in the new text
    lost = [v for v in _slot_values(slots) if v in original and v not in candidate]
    checks.append(_check("slots_preserved", not lost, "missing or changed: " + ", ".join(lost) if lost else ""))

    # 3. no number that was not in the approved text
    allowed = set(_DIGITS.findall(original))
    extra = sorted(set(_DIGITS.findall(candidate)) - allowed)
    checks.append(_check("no_new_numbers", not extra, "new numbers: " + ", ".join(extra) if extra else ""))

    # 4. blocked diagnosis and alarm words
    hits = find_blocked(candidate, language)
    checks.append(_check("no_blocked_words", not hits, "blocked: " + ", ".join(hits) if hits else ""))

    # 5. length within the channel limit
    limit = max_length if max_length else int(len(original) * 1.25) + 10
    checks.append(_check("length_within_limit", len(candidate) <= limit, f"{len(candidate)} of {limit}"))

    # 6. script and language
    checks.append(_script_check(candidate, language, slots))

    failed = [c for c in checks if not c["passed"]]
    reason = None
    if failed:
        reason = "; ".join(c["name"] + (f" ({c['detail']})" if c["detail"] else "") for c in failed)
    return {"passed": not failed, "failed_reason": reason, "checks": checks}


def _script_check(text: str, language: str, slots: dict) -> dict:
    body = text
    for v in sorted(_slot_values(slots), key=len, reverse=True):
        body = body.replace(v, " ")  # names and places in slots may legitimately be in another script
    arabic = len(_ARABIC.findall(body))
    latin = len(_LATIN.findall(body))
    letters = arabic + latin
    if letters == 0:
        return _check("script_matches_language", False, "no letters")
    if language == "ar":
        return _check("script_matches_language", arabic / letters >= 0.8, f"arabic share {arabic / letters:.2f}")
    if arabic / letters > 0.05:
        return _check("script_matches_language", False, "unexpected Arabic script")
    words = [w.lower() for w in _WORDS.findall(body)]
    own = sum(w in _STOP[language] for w in words)
    other_lang = "fr" if language == "en" else "en"
    other = sum(w in _STOP[other_lang] for w in words)
    ok = not (other >= 3 and other > own)
    return _check("script_matches_language", ok, f"{language} stopwords {own}, {other_lang} stopwords {other}")
