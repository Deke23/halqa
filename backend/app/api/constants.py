"""Single constant for the product name on the backend. Do not hard-code it elsewhere."""

from pathlib import Path

APP_NAME = "Halqa"

# Locate shared directories relative to the backend package, never the working directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
FRONTEND_DIST = REPO_DIR / "frontend" / "dist"
DOCS_DIR = REPO_DIR / "docs"
DATA_DIR = BACKEND_DIR / "data"
