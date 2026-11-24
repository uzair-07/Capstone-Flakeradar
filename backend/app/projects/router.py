"""Projects and API tokens, managed by the logged-in owner."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import current_user, owned_project
from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.session import get_db
from app.models import ApiToken, Project, User
from app.projects.service import create_project, create_token
from app.runs.schemas import ProjectOut

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=100)
    default_branch: str = Field(default="main", min_length=1, max_length=255)


class TokenIn(BaseModel):
    name: str = Field(default="ci", min_length=1, max_length=100)


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class NewTokenOut(TokenOut):
    token: str = Field(description="Shown once. Store it as a CI secret.")


@router.get("/projects", response_model=list[ProjectOut], summary="Your projects")
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    query = select(Project).where(Project.owner_id == user.id).order_by(Project.name)
    return list(db.scalars(query))


@router.post("/projects", response_model=ProjectOut, status_code=201, summary="Create a project")
def new_project(
    body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Project:
    try:
        project = create_project(db, body.name, body.slug)
    except ValueError as exc:
        message = str(exc)
        if "already exists" in message:
            raise ConflictError(message) from exc
        raise AppError(message) from exc
    project.owner_id = user.id
    project.default_branch = body.default_branch.strip()
    db.commit()
    return project


@router.get("/projects/{slug}/tokens", response_model=list[TokenOut], summary="API tokens")
def list_tokens(
    slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list:
    project = owned_project(db, user, slug)
    return list(
        db.scalars(
            select(ApiToken).where(ApiToken.project_id == project.id).order_by(ApiToken.created_at)
        )
    )


@router.post(
    "/projects/{slug}/tokens", response_model=NewTokenOut, status_code=201, summary="New token"
)
def new_token(
    slug: str,
    body: TokenIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> NewTokenOut:
    project = owned_project(db, user, slug)
    token = create_token(db, project, body.name)
    db.commit()
    record = db.scalar(select(ApiToken).where(ApiToken.prefix == token.prefix))
    return NewTokenOut(**TokenOut.model_validate(record).model_dump(), token=token.value)


@router.delete("/projects/{slug}/tokens/{token_id}", status_code=204, summary="Revoke a token")
def revoke_token(
    slug: str,
    token_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    project = owned_project(db, user, slug)
    token = db.get(ApiToken, token_id)
    if token is None or token.project_id != project.id:
        raise NotFoundError("No such token in this project.")
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        db.commit()
