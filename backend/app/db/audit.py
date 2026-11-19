"""Database-level protection of the audit log, plus a small additive schema upgrade.

Safety property: `case_events` rejects UPDATE and DELETE inside the database itself, so the guarantee does not
depend on the ORM guard in models.py. SQLite gets two triggers. PostgreSQL gets one trigger function and a trigger
for row UPDATE and DELETE and one for TRUNCATE.

The demo reset (`Database.reset_schema`) drops and recreates the tables. That is DDL, not a row UPDATE or DELETE,
so the triggers do not stand in its way. Dropping the table drops its triggers; they are created again right after.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .models import Base

TABLE = "case_events"

_SQLITE = (
    f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_update BEFORE UPDATE ON {TABLE} "
    f"BEGIN SELECT RAISE(ABORT, 'case_events is append-only: UPDATE refused'); END",
    f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_delete BEFORE DELETE ON {TABLE} "
    f"BEGIN SELECT RAISE(ABORT, 'case_events is append-only: DELETE refused'); END",
)

_POSTGRES = (
    f"""CREATE OR REPLACE FUNCTION {TABLE}_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'case_events is append-only: % refused', TG_OP;
END;
$$ LANGUAGE plpgsql""",
    f"DROP TRIGGER IF EXISTS {TABLE}_no_change ON {TABLE}",
    f"CREATE TRIGGER {TABLE}_no_change BEFORE UPDATE OR DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION {TABLE}_append_only()",
    f"DROP TRIGGER IF EXISTS {TABLE}_no_truncate ON {TABLE}",
    f"CREATE TRIGGER {TABLE}_no_truncate BEFORE TRUNCATE ON {TABLE} FOR EACH STATEMENT EXECUTE FUNCTION {TABLE}_append_only()",
)


def install_audit_triggers(engine: Engine) -> None:
    """Create the append-only triggers for the engine's dialect. Safe to call repeatedly."""
    dialect = engine.dialect.name
    if dialect == "sqlite":
        statements = _SQLITE
    elif dialect == "postgresql":
        statements = _POSTGRES
    else:
        return
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt.replace("%", "%%") if dialect == "postgresql" else stmt)


def add_missing_columns(engine: Engine) -> list[str]:
    """Additive upgrade for databases created by an earlier version: add model columns the table lacks.

    Only nullable columns or columns with a server default are added. Returns the columns that were added.
    """
    added: list[str] = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                if not col.nullable and col.server_default is None:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(dialect=engine.dialect)}'
                if col.server_default is not None:
                    ddl += f" DEFAULT {col.server_default.arg.compile(dialect=engine.dialect)}"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    return added
