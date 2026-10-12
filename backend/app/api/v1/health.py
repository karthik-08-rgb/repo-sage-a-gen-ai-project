import time
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings

router = APIRouter(tags=["Health & Observability"])

START_TIME = time.time()


@router.get("/health")
def health_check():
    """Basic liveness probe."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "uptime_seconds": round(time.time() - START_TIME, 2)
    }


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe checking database connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    if not db_ok:
        return {"status": "unready", "database": "disconnected"}

    return {
        "status": "ready",
        "database": "connected",
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER
    }


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """System metrics and telemetry summary."""
    from app.models.repository import Repository
    from app.models.code_chunk import CodeChunk
    from app.models.ingestion_job import IngestionJob

    total_repos = db.query(Repository).count()
    total_chunks = db.query(CodeChunk).count()
    failed_jobs = db.query(IngestionJob).filter(IngestionJob.status == "failed").count()
    completed_jobs = db.query(IngestionJob).filter(IngestionJob.status == "completed").count()

    return {
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "total_repositories": total_repos,
        "total_code_chunks": total_chunks,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "job_failure_rate": round(failed_jobs / max(1, completed_jobs + failed_jobs), 4)
    }
