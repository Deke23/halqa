"""Optional LLM providers, plain httpx, 10 second timeout. They only return text; the caller validates it."""
from __future__ import annotations

import os

import httpx

TIMEOUT_S = 10.0
LANGUAGE_NAMES = {"en": "English", "ar": "Modern Standard Arabic", "fr": "French"}


def system_prompt(language: str, tone: str | None) -> str:
    return (
        "You re-word approved health messages. You will receive one approved message. "
        f"Re-write it in {LANGUAGE_NAMES.get(language, language)}, in a {tone or 'warm and plain'} tone, at a reading level of about age 12. "
        "Rules: keep the meaning exactly. Do not add facts, advice, numbers, dates, names or diagnoses. "
        "Do not remove any number, date, time, name or phone value, and do not change how they are written. "
        "Do not use the words hypertension or diagnosis, and do not use alarming or blaming words. "
        "Do not mention family or lifestyle. Return only the re-worded message text, with no preface and no quotes."
    )


def call_provider(provider: str, system: str, text: str) -> str:
    if provider == "azure_openai":
        return _azure(system, text)
    if provider == "anthropic":
        return _anthropic(system, text)
    raise ValueError(f"Unknown wording provider: {provider!r}")


def _azure(system: str, text: str) -> str:
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01")
    resp = httpx.post(
        f"{endpoint}/openai/deployments/{deployment}/chat/completions",
        params={"api-version": version},
        headers={"api-key": os.environ["AZURE_OPENAI_API_KEY"], "Content-Type": "application/json"},
        json={"messages": [{"role": "system", "content": system}, {"role": "user", "content": text}], "temperature": 0.2},
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _anthropic(system: str, text: str) -> str:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": os.environ.get("WORDING_MODEL", "claude-haiku-5-5"),
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": text}],
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    return "".join(b.get("text", "") for b in resp.json()["content"] if b.get("type") == "text")
