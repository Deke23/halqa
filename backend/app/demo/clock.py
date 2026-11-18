"""Demo clock: real time plus an adjustable offset stored in the database.

Engine functions never read this; the API reads `now` here and passes it in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import DemoClock


def real_now() -> datetime:
    return datetime.now(timezone.utc)


def _row(db: Session) -> DemoClock:
    row = db.get(DemoClock, 1)
    if row is None:
        row = DemoClock(id=1, offset_seconds=0.0)
        db.add(row)
        db.flush()
    return row


def offset_seconds(db: Session) -> float:
    return _row(db).offset_seconds


def now(db: Session) -> datetime:
    return real_now() + timedelta(seconds=_row(db).offset_seconds)


def advance(db: Session, hours: float) -> datetime:
    row = _row(db)
    row.offset_seconds += hours * 3600
    db.flush()
    return now(db)


def reset(db: Session) -> None:
    _row(db).offset_seconds = 0.0
    db.flush()
