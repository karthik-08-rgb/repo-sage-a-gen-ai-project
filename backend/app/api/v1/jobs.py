from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user, get_user_repository
from app.models.user import User
from app.models.repository import Repository
from app.models.ingestion_job import IngestionJob
from app.schemas.job import IngestionJobResponse
from app.schemas.common import APIResponse

router = APIRouter(tags=["Background Ingestion Jobs"])


@router.get("/jobs/{job_id}", response_model=APIResponse[IngestionJobResponse])
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve status, stage, and progress of an ingestion job."""
    job = db.query(IngestionJob).join(Repository).filter(
        IngestionJob.id == job_id,
        Repository.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return APIResponse(
        success=True,
        message="Job retrieved",
        data=IngestionJobResponse.model_validate(job)
    )


@router.get("/repositories/{repository_id}/jobs", response_model=APIResponse[List[IngestionJobResponse]])
def get_repository_jobs(
    repo: Repository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """Get ingestion history for a specific repository."""
    jobs = db.query(IngestionJob).filter(
        IngestionJob.repository_id == repo.id
    ).order_by(IngestionJob.started_at.desc()).all()

    return APIResponse(
        success=True,
        message="Jobs retrieved",
        data=[IngestionJobResponse.model_validate(j) for j in jobs]
    )
