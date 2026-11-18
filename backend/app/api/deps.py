"""Request dependencies: database session, current user, role guards, case visibility."""

from __future__ import annotations

from collections.abc import Iterator

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Case, EConsult, Referral, User
from app.demo import clock
from app.engine.types import Role

from . import auth
from .core import ApiError


def get_db(request: Request) -> Iterator[Session]:
    db: Session = request.app.state.db.session()
    try:
        yield db
    finally:
        db.close()


def current_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "NOT_AUTHENTICATED", "Send a Bearer guest token.")
    try:
        claims = auth.decode(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as exc:
        raise ApiError(401, "INVALID_TOKEN", "The token is invalid or expired.") from exc
    user = db.get(User, int(claims["sub"]))
    if user is None:
        raise ApiError(401, "UNKNOWN_USER", "The token's user no longer exists. Start a new guest session.")
    return user


def role_of(user: User) -> Role:
    return Role(user.role)


def require_roles(*roles: Role):
    def dep(user: User = Depends(current_user)) -> User:
        if role_of(user) not in roles:
            raise ApiError(403, "FORBIDDEN_ROLE", f"The {user.role} role cannot use this route.")
        return user
    return dep


staff = require_roles(Role.COORDINATOR, Role.CLINICIAN)
anyone_but_patient = require_roles(Role.COORDINATOR, Role.CLINICIAN, Role.ANALYST)
patient_only = require_roles(Role.PATIENT)
clinician_only = require_roles(Role.CLINICIAN)


def can_view(db: Session, user: User, case: Case) -> bool:
    if user.role == "patient":
        return user.patient_id == case.patient_id
    if user.role == "coordinator":
        return user.region == case.region
    if user.role == "clinician":
        if user.organisation == case.organisation or case.owner_user_id == user.id:
            return True
        if db.scalars(select(Referral.id).where(Referral.case_id == case.id, Referral.to_user_id == user.id)).first():
            return True
        q = select(EConsult.id).where(EConsult.case_id == case.id, (EConsult.to_user_id == user.id) | (EConsult.from_user_id == user.id))
        return db.scalars(q).first() is not None
    return False


def load_case(db: Session, user: User, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise ApiError(404, "CASE_NOT_FOUND", "No such case.")
    if not can_view(db, user, case):
        raise ApiError(403, "NO_ACCESS", "You do not have access to this case.")
    return case


def now_of(db: Session):
    return clock.now(db)
