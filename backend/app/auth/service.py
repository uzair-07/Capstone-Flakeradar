"""Accounts and browser sessions (a signed JWT in an httpOnly cookie)."""

import re
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import Project, User

SESSION_COOKIE = "flakeradar_session"
ALGORITHM = "HS256"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 10
# Compared against when the email is unknown, so both cases take the same time.
_DUMMY_HASH = hash_password("not-a-real-password")


def normalise_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, email: str, password: str) -> User:
    if not get_settings().allow_registration:
        raise ForbiddenError("Registration is closed on this server.")
    email = normalise_email(email)
    if not EMAIL_PATTERN.match(email) or len(email) > 320:
        raise AppError("Enter a valid email address.")
    if len(password) < MIN_PASSWORD:
        raise AppError(f"Use a password of at least {MIN_PASSWORD} characters.")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise ConflictError("An account with this email already exists. Log in instead.")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise UnauthorizedError("Email or password is incorrect.")
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError("Email or password is incorrect.")
    return user


def start_session(response: Response, user: User) -> None:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    token = jwt.encode(
        {"sub": str(user.id), "exp": expires, "iat": datetime.now(UTC)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def end_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: the logged-in user, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise UnauthorizedError("Log in to continue.")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Your session has expired. Log in again.") from exc
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Your session has expired. Log in again.")
    return user


def owned_project(db: Session, user: User, slug: str) -> Project:
    """A project the user owns. Other users' projects look like they do not exist."""
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None or project.owner_id != user.id:
        raise NotFoundError(f"No project with slug '{slug}'.")
    return project
