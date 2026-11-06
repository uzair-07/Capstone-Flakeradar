"""Raw report storage on the local filesystem (a Docker volume in production)."""

import os
import uuid
from pathlib import Path

from app.core.config import get_settings


def _root() -> Path:
    return get_settings().upload_dir.resolve()


def save_report(project_id: uuid.UUID, upload_id: uuid.UUID, content: bytes) -> str:
    """Write the file atomically and return its path relative to the upload root."""
    relative = Path(str(project_id)) / f"{upload_id}.xml"
    target = _root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, target)
    return relative.as_posix()


def read_report(relative_path: str) -> bytes:
    root = _root()
    path = (root / relative_path).resolve()
    if root not in path.parents:
        raise ValueError("Upload path escapes the upload directory")
    return path.read_bytes()


def delete_report(relative_path: str) -> None:
    path = _root() / relative_path
    path.unlink(missing_ok=True)
