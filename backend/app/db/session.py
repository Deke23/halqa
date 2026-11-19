"""Engine and session factory. SQLite file by default, PostgreSQL when DATABASE_URL is set."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .audit import add_missing_columns, install_audit_triggers
from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "halqa.db"


def resolve_url(url: str | None = None) -> str:
    """Explicit url, else DATABASE_URL, else SQLITE_PATH, else backend/halqa.db."""
    url = url or os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    path = Path(os.environ.get("SQLITE_PATH") or DEFAULT_DB_PATH)
    return f"sqlite:///{path.as_posix()}"


class Database:
    def __init__(self, url: str | None = None) -> None:
        self.url = resolve_url(url)
        kwargs: dict = {}
        if self.url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if self.url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
        self.engine: Engine = create_engine(self.url, **kwargs)
        if self.url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _fk_on(dbapi_conn, _):  # noqa: ANN001
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        self.sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        """Create missing tables, add columns an older database lacks, and (re)install the audit-log triggers."""
        Base.metadata.create_all(self.engine)
        add_missing_columns(self.engine)
        install_audit_triggers(self.engine)

    def reset_schema(self) -> None:
        """Drop and recreate every table and the audit-log triggers (demo reset only).

        This is DDL. The append-only triggers on case_events guard UPDATE and DELETE rows; they do not stop a DROP TABLE,
        so dropping the schema is the one and only way audit events are ever removed. Never call this outside the demo.
        """
        with self.engine.connect() as conn:
            if self.url.startswith("sqlite"):
                conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            Base.metadata.drop_all(conn)
            conn.commit()
            if self.url.startswith("sqlite"):
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        self.create_all()

    def session(self) -> Session:
        return self.sessionmaker()
