import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError
from app.core.logging import log_fields
from app.ingest import storage
from app.models import Project, Upload
from app.worker.queue import enqueue_upload

logger = logging.getLogger(__name__)


def find_duplicate(db: Session, project: Project, checksum: str) -> Upload | None:
    return db.scalar(
        select(Upload).where(Upload.project_id == project.id, Upload.checksum == checksum)
    )


def accept_upload(
    db: Session,
    project: Project,
    content: bytes,
    *,
    commit_sha: str | None,
    branch: str | None,
    ci_run_id: str | None,
    attempt: int,
) -> tuple[Upload, bool]:
    """Store the file, record it and queue it for parsing.

    Returns (upload, created). Sending a file that was already received returns the original
    upload with created=False, so CI retries never create duplicate runs.
    """
    checksum = hashlib.sha256(content).hexdigest()
    existing = find_duplicate(db, project, checksum)
    if existing is not None:
        return existing, False

    upload_id = uuid.uuid4()
    path = storage.save_report(project.id, upload_id, content)
    upload = Upload(
        id=upload_id,
        project_id=project.id,
        checksum=checksum,
        file_path=path,
        size_bytes=len(content),
        commit_sha=commit_sha,
        branch=branch,
        ci_run_id=ci_run_id,
        attempt=attempt,
    )
    db.add(upload)
    try:
        db.commit()
    except IntegrityError:
        # The same file arrived twice at the same moment; keep the first.
        db.rollback()
        storage.delete_report(path)
        existing = find_duplicate(db, project, checksum)
        if existing is None:
            raise
        return existing, False

    try:
        enqueue_upload(str(upload.id))
    except Exception as exc:
        # Without a queued job the upload would never be processed; undo it so a retry works.
        logger.exception("Could not queue upload", extra=log_fields(upload_id=str(upload.id)))
        db.delete(upload)
        db.commit()
        storage.delete_report(path)
        raise ServiceUnavailableError(
            "The processing queue is unavailable. Retry the upload in a minute."
        ) from exc

    logger.info(
        "Upload accepted",
        extra=log_fields(upload_id=str(upload.id), project=project.slug, bytes=len(content)),
    )
    return upload, True
