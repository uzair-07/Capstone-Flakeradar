import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, PayloadTooLargeError
from app.db.session import get_db
from app.ingest.schemas import UploadOut
from app.ingest.service import accept_upload
from app.models import CiRun, Upload
from app.projects.service import authenticate_token, get_project_by_slug, require_project_token

router = APIRouter(tags=["ingest"])

CHUNK_BYTES = 64 * 1024


def _read_limited(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := file.file.read(CHUNK_BYTES):
        size += len(chunk)
        if size > limit:
            raise PayloadTooLargeError(
                f"Reports may be at most {limit // (1024 * 1024)} MB. Split large suites "
                "into several files."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _to_out(db: Session, upload: Upload, duplicate: bool = False) -> UploadOut:
    out = UploadOut.model_validate(upload)
    out.run_id = db.scalar(select(CiRun.id).where(CiRun.upload_id == upload.id))
    out.duplicate = duplicate
    return out


@router.post(
    "/projects/{project_slug}/uploads",
    status_code=202,
    response_model=UploadOut,
    summary="Upload a JUnit XML report from CI",
)
def upload_report(
    project_slug: str,
    file: Annotated[UploadFile, File(description="JUnit XML report")],
    commit_sha: Annotated[str | None, Form(max_length=64)] = None,
    branch: Annotated[str | None, Form(max_length=255)] = None,
    ci_run_id: Annotated[str | None, Form(max_length=255)] = None,
    attempt: Annotated[int, Form(ge=1, le=1000)] = 1,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    project = get_project_by_slug(db, project_slug)
    require_project_token(db, authorization, project)
    content = _read_limited(file, get_settings().max_upload_bytes)
    upload, created = accept_upload(
        db,
        project,
        content,
        commit_sha=commit_sha or None,
        branch=branch or None,
        ci_run_id=ci_run_id or None,
        attempt=attempt,
    )
    db.commit()  # persists the token's last_used_at
    body = _to_out(db, upload, duplicate=not created)
    return JSONResponse(body.model_dump(mode="json"), status_code=202 if created else 200)


@router.get("/uploads/{upload_id}", response_model=UploadOut, summary="Processing status")
def get_upload(
    upload_id: uuid.UUID,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> UploadOut:
    token = authenticate_token(db, authorization)
    upload = db.get(Upload, upload_id)
    if upload is None or upload.project_id != token.project_id:
        raise NotFoundError("No such upload for this token's project.")
    db.commit()
    return _to_out(db, upload)
