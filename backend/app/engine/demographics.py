"""Reporting bands and codes shared by the live dashboard and the simulation (one definition, no private copies).

Pure data and pure functions. The simulation may import this module; the engine never imports the simulation.
"""

from __future__ import annotations

AGE_BANDS: tuple[tuple[int, int, str], ...] = ((18, 34, "18-34"), (35, 49, "35-49"), (50, 64, "50-64"), (65, 200, "65+"))
AGE_BAND_LABELS: tuple[str, ...] = tuple(label for _, _, label in AGE_BANDS)

# Sex codes as stored on the patient record and used by the dashboard split.
SEX_CODES: tuple[str, ...] = ("F", "M")


def age_band(age: int) -> str:
    """Band label for an adult age. Ages under 18 fall into the first band."""
    for lo, hi, label in AGE_BANDS:
        if age <= hi:
            return label
    return AGE_BANDS[-1][2]
