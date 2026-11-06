from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.db.session import get_db
from app.worker.queue import get_health_redis

router = APIRouter(tags=["operations"])


@router.get("/healthz", summary="The process is running")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz", summary="Database and queue are reachable")
def readyz(db: Session = Depends(get_db)) -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        get_health_redis().ping()
        checks["queue"] = "ok"
    except Exception:
        checks["queue"] = "unavailable"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ok" if ready else "unavailable", "checks": checks},
        status_code=200 if ready else 503,
    )
