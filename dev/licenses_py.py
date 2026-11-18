"""Print a Markdown table of the direct Python dependencies in backend/requirements.txt.

Standard library only. Reads the installed metadata with importlib.metadata, so run it
where the packages are installed (the dev container).
"""

import re
from importlib import metadata
from pathlib import Path

REQ_FILE = Path(__file__).resolve().parent.parent / "backend" / "requirements.txt"
NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
MISSING = "unknown"


def direct_names(path):
    names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = NAME_RE.match(line)
        if match:
            names.append(match.group(1))
    return names


def clean(value):
    """Collapse whitespace and escape pipes so the value fits in one table cell."""
    if not value:
        return MISSING
    value = " ".join(str(value).split())
    return value.replace("|", "\\|") if value else MISSING


def usable(value):
    # Some packages write the placeholder UNKNOWN into the License field.
    if value is None:
        return None
    value = " ".join(str(value).split())
    if not value or value.upper() == "UNKNOWN":
        return None
    return value


def licence_of(meta):
    lic = usable(meta.get("License-Expression")) or usable(meta.get("License"))
    if lic:
        return lic
    classifiers = [
        c.split("::", 1)[1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    return None


def url_of(meta):
    home = usable(meta.get("Home-page"))
    if home:
        return home
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("homepage", "home", "home-page", "source", "repository"):
            if url.strip():
                return url.strip()
    for entry in meta.get_all("Project-URL") or []:
        _, _, url = entry.partition(",")
        if url.strip():
            return url.strip()
    return None


def main():
    rows = []
    for name in direct_names(REQ_FILE):
        try:
            version = metadata.version(name)
            meta = metadata.metadata(name)
        except metadata.PackageNotFoundError:
            version, meta = None, None
        lic = licence_of(meta) if meta is not None else None
        url = url_of(meta) if meta is not None else None
        rows.append((name, version, lic, url))

    print("| Package | Version | Licence | URL |")
    print("| --- | --- | --- | --- |")
    for name, version, lic, url in rows:
        print(f"| {clean(name)} | {clean(version)} | {clean(lic)} | {clean(url)} |")


if __name__ == "__main__":
    main()
