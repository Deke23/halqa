"""Loader for engine/config.yaml, the only place thresholds and service levels live."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).with_name("config.yaml")
_HOURS_PER_UNIT = {"hours": 1.0, "days": 24.0}


@dataclass(frozen=True)
class ConfigEntry:
    section: str
    key: str
    value: Any
    unit: str
    basis: str
    status: str


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, dict[str, Any]]]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    for section, entries in raw.items():
        for key, entry in entries.items():
            missing = {"value", "unit", "basis", "status"} - set(entry)
            if missing:
                raise ValueError(f"config {section}.{key} is missing {sorted(missing)}")
    return raw


def value(section: str, key: str) -> Any:
    return _load()[section][key]["value"]


def hours(section: str, key: str) -> float:
    """Return a duration entry converted to hours."""
    entry = _load()[section][key]
    return float(entry["value"]) * _HOURS_PER_UNIT[entry["unit"]]


def all_entries() -> list[ConfigEntry]:
    return [
        ConfigEntry(section, key, e["value"], e["unit"], e["basis"], e["status"])
        for section, entries in _load().items()
        for key, e in entries.items()
    ]
