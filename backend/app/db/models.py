"""SQLAlchemy 2 models.

Safety property: CaseEvent is append-only. The ORM listeners below refuse any update
or delete of an event row, and no code path in the application attempts one. The demo
reset drops and recreates the schema (DDL), which is the only way events disappear.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, event
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Stores naive UTC, always returns timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime refused; use UTC-aware datetimes")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime(), dict[str, Any]: JSON, list[Any]: JSON}


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(40), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    initials: Mapped[str] = mapped_column(String(8))
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(10))
    nationality_group: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(5))
    region: Mapped[str] = mapped_column(String(10))
    insurance: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(12))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    organisation: Mapped[str] = mapped_column(String(120))
    primary_clinician_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", use_alter=True, name="fk_patient_primary_clinician"), nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    persona_key: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    region: Mapped[str] = mapped_column(String(10))
    organisation: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(5), default="en")
    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id", use_alter=True, name="fk_user_patient"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(300), default="")


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    region: Mapped[str] = mapped_column(String(10), index=True)
    organisation: Mapped[str] = mapped_column(String(120))
    scenario: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state: Mapped[str] = mapped_column(String(24), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    index_systolic: Mapped[int] = mapped_column(Integer)
    index_diastolic: Mapped[int] = mapped_column(Integer)
    source_system: Mapped[str] = mapped_column(String(40))
    opened_at: Mapped[datetime]
    milestones: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    step_started_at: Mapped[datetime]
    owner_role: Mapped[str] = mapped_column(String(20))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    urgent_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    urgent_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    urgent_review_done_at: Mapped[datetime | None] = mapped_column(nullable=True)
    urgent_review_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    referral_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    confirmation_method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    suggested_closure_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    needs_clinician_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    unreachable_stage: Mapped[int] = mapped_column(Integer, default=0)
    teach_back_failures: Mapped[int] = mapped_column(Integer, default=0)
    teach_back_first_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    patient_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visit_outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    state_before_close: Mapped[str | None] = mapped_column(String(24), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closure_evidence_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    closure_evidence_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    closure_decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship()


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    systolic: Mapped[int] = mapped_column(Integer)
    diastolic: Mapped[int] = mapped_column(Integer)
    pulse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    taken_at: Mapped[datetime]
    source: Mapped[str] = mapped_column(String(12))
    entered_by_role: Mapped[str] = mapped_column(String(20))
    entered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    to_service: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12))
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Slot(Base):
    __tablename__ = "slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(10), index=True)
    starts_at: Mapped[datetime]
    provider_name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(160))
    clinician_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    booked: Mapped[bool] = mapped_column(Boolean, default=False)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"), nullable=True)
    starts_at: Mapped[datetime]
    provider_name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(12), default="BOOKED")
    created_at: Mapped[datetime]


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    direction: Mapped[str] = mapped_column(String(4))  # OUT to patient, IN from patient
    channel: Mapped[str] = mapped_column(String(12))
    language: Mapped[str] = mapped_column(String(5))
    text: Mapped[str] = mapped_column(Text)
    template_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(14), default="TEMPLATE")
    sender_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]


class EConsult(Base):
    __tablename__ = "econsults"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    created_at: Mapped[datetime]
    answered_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str | None] = mapped_column(String(12), nullable=True)
    granted: Mapped[bool] = mapped_column(Boolean)
    granted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(nullable=True)


class PlanWeek(Base):
    __tablename__ = "plan_weeks"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    week_index: Mapped[int] = mapped_column(Integer)
    action_key: Mapped[str] = mapped_column(String(20))
    size: Mapped[str] = mapped_column(String(10))
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)  # null while open
    barrier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    offered_larger: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_recorded: Mapped[bool] = mapped_column(Boolean, default=False)
    starts_at: Mapped[datetime]
    checked_in_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    title_key: Mapped[str] = mapped_column(String(80))
    owner_role: Mapped[str] = mapped_column(String(20))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    created_at: Mapped[datetime]
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    at: Mapped[datetime]
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(20))  # user id as text, or "system"
    actor_role: Mapped[str] = mapped_column(String(20))
    type: Mapped[str] = mapped_column(String(40), index=True)
    from_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DemoClock(Base):
    __tablename__ = "demo_clock"
    id: Mapped[int] = mapped_column(primary_key=True)
    offset_seconds: Mapped[float] = mapped_column(Float, default=0.0)


class AppendOnlyError(RuntimeError):
    pass


@event.listens_for(CaseEvent, "before_update")
def _refuse_event_update(mapper, connection, target):  # noqa: ANN001
    raise AppendOnlyError("case_events is append-only; updates are not allowed")


@event.listens_for(CaseEvent, "before_delete")
def _refuse_event_delete(mapper, connection, target):  # noqa: ANN001
    raise AppendOnlyError("case_events is append-only; deletes are not allowed")
