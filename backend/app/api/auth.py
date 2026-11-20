"""Stateless signed guest tokens (HS256). The secret comes from GUEST_TOKEN_SECRET."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt

DEV_SECRET = "dev-only-guest-token-secret-change-me-0123456789"
TOKEN_HOURS = 24


def _secret() -> str:
    return os.environ.get("GUEST_TOKEN_SECRET") or DEV_SECRET


def issue(user_id: int, persona: str | None, role: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "persona": persona, "role": role, "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(claims, _secret(), algorithm="HS256")


def decode(token: str) -> dict:
    # The issued-at claim is informational. Checking it rejects a fresh token whenever the host
    # clock is stepped back by a time sync (seen on virtualised hosts), so only expiry is
    # enforced, with a small leeway for clock skew between instances.
    return jwt.decode(token, _secret(), algorithms=["HS256"], leeway=120, options={"verify_iat": False})
