"""Write docs/openapi.json from the app without touching a real database or starting a server.

Run from backend/:  python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.api.constants import DOCS_DIR  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> None:
    app = create_app("sqlite://", seed_on_start=False, start_tick=False)  # in-memory, never the demo database
    target = DOCS_DIR / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
