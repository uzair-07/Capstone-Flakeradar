import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import NewToken, bearer_token, generate_token, token_matches, token_prefix
from app.models import ApiToken, Project

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "project"


def create_project(db: Session, name: str, slug: str | None = None) -> Project:
    slug = slug or slugify(name)
    if not SLUG_PATTERN.match(slug):
        raise ValueError("Slug may contain lowercase letters, digits and single hyphens only.")
    if db.scalar(select(Project).where(Project.slug == slug)) is not None:
        raise ValueError(f"A project with slug '{slug}' already exists.")
    project = Project(name=name.strip()[:100], slug=slug)
    db.add(project)
    db.flush()
    return project


def create_token(db: Session, project: Project, name: str = "ci") -> NewToken:
    token = generate_token()
    db.add(ApiToken(project_id=project.id, name=name[:100], prefix=token.prefix,
                    token_hash=token.hash))
    db.flush()
    return token


def get_project_by_slug(db: Session, slug: str) -> Project:
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise NotFoundError(f"No project with slug '{slug}'.")
    return project


def authenticate_token(db: Session, authorization: str | None) -> ApiToken:
    """Resolve an `Authorization: Bearer fr_...` header to an active project token."""
    raw = bearer_token(authorization)
    if raw is None:
        raise UnauthorizedError("Send a project API token as 'Authorization: Bearer <token>'.")
    prefix = token_prefix(raw)
    token = db.scalar(select(ApiToken).where(ApiToken.prefix == prefix)) if prefix else None
    if token is None or token.revoked_at is not None or not token_matches(raw, token.token_hash):
        raise UnauthorizedError("The API token is invalid or has been revoked.")
    token.last_used_at = datetime.now(UTC)
    return token


def require_project_token(db: Session, authorization: str | None, project: Project) -> ApiToken:
    token = authenticate_token(db, authorization)
    if token.project_id != project.id:
        raise ForbiddenError("This API token belongs to a different project.")
    return token
