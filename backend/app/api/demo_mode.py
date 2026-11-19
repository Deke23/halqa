"""The DEMO_MODE switch. Default true so the prototype behaves as a demo.

When false, guest login, the clock advance, the reset and the intake simulator are disabled.
The value is read on every request, so a test or an operator can change it without a restart.
"""

from __future__ import annotations

import os

from .core import ApiError

_FALSE = {"0", "false", "no", "off"}


def demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "true").strip().lower() not in _FALSE


def require_demo() -> None:
    """Route dependency for demo-only routes."""
    if not demo_mode():
        raise ApiError(403, "DEMO_MODE_OFF", "This control is only available when DEMO_MODE is on.")
