"""Background jobs executed by the RQ worker."""

import logging
import uuid
from datetime import UTC, datetime

from rq import get_current_job
from sqlalchemy.orm import Session

from app.core.logging import log_fields
from app.db.session import session_scope
from app.ingest import storage
from app.ingest.junit import JUnitParseError, parse_junit_xml
from app.ingest.processing import store_report
from app.models import Upload, UploadStatus

logger = logging.getLogger(__name__)


def _is_last_attempt() -> bool:
    job = get_current_job()
    return job is None or not job.retries_left


def process_upload(upload_id: str) -> dict[str, object]:
    """Parse one uploaded report and store its results. Safe to run more than once."""
    with session_scope() as db:
        upload = db.get(Upload, uuid.UUID(upload_id))
        if upload is None:
            logger.warning("Upload not found", extra=log_fields(upload_id=upload_id))
            return {"status": "missing"}
        if upload.status == UploadStatus.DONE:
            return {"status": UploadStatus.DONE, "skipped": True}

        upload.status = UploadStatus.PROCESSING
        db.commit()

        try:
            report = parse_junit_xml(storage.read_report(upload.file_path))
            run = store_report(db, upload, report)
            upload.status = UploadStatus.DONE
            upload.error = None
            upload.processed_at = datetime.now(UTC)
            db.commit()
        except JUnitParseError as exc:
            db.rollback()
            _mark(db, upload_id, UploadStatus.FAILED, str(exc))
            logger.info("Upload rejected", extra=log_fields(upload_id=upload_id, reason=str(exc)))
            return {"status": UploadStatus.FAILED, "error": str(exc)}
        except Exception as exc:
            db.rollback()
            if _is_last_attempt():
                _mark(db, upload_id, UploadStatus.FAILED, "Processing failed after retries.")
            else:
                _mark(db, upload_id, UploadStatus.RECEIVED, f"Retrying after error: {exc}")
            logger.exception("Upload processing error", extra=log_fields(upload_id=upload_id))
            raise

        logger.info(
            "Upload processed",
            extra=log_fields(upload_id=upload_id, run_id=str(run.id), tests=run.total),
        )
        return {"status": UploadStatus.DONE, "run_id": str(run.id), "tests": run.total}


def _mark(db: Session, upload_id: str, status: UploadStatus, error: str) -> None:
    upload = db.get(Upload, uuid.UUID(upload_id))
    if upload is not None:
        upload.status = status
        upload.error = error[:2000]
        upload.processed_at = datetime.now(UTC)
        db.commit()
