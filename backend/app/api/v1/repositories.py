import os
import shutil
import tempfile
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user, get_user_repository
from app.models.user import User
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.ingestion_job import IngestionJob
from app.schemas.repository import (
    RepositoryCreateGitHub,
    RepositoryResponse,
    RepositoryStatusResponse,
    RepositoryFileItem,
    FileContentResponse,
)
from app.schemas.common import APIResponse
from app.services.repository.repo_service import RepositoryService
from app.workers.tasks import process_repository_ingestion

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.post("", response_model=APIResponse[RepositoryResponse], status_code=status.HTTP_201_CREATED)
def add_github_repository(
    req: RepositoryCreateGitHub,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new GitHub repository (public or private) and trigger background indexing."""
    repo = RepositoryService.create_github_repo(
        db=db,
        user=current_user,
        name=req.name,
        url=req.url,
        branch=req.branch or "main",
        access_token=req.access_token
    )
    # Trigger background indexing
    background_tasks.add_task(process_repository_ingestion, repo.id, req.access_token)

    return APIResponse(
        success=True,
        message="Repository registered. Ingestion started in background.",
        data=RepositoryResponse.model_validate(repo)
    )


@router.post("/upload-zip", response_model=APIResponse[RepositoryResponse], status_code=status.HTTP_201_CREATED)
async def upload_zip_repository(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a ZIP archive and trigger indexing."""
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be a .zip file.")

    # Save to temporary file safely
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        repo = RepositoryService.create_zip_repo(
            db=db,
            user=current_user,
            name=name,
            zip_tmp_path=tmp_path
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Ingest extracted files in background
    background_tasks.add_task(process_repository_ingestion, repo.id, None)

    return APIResponse(
        success=True,
        message="ZIP repository uploaded and extracted. Indexing started.",
        data=RepositoryResponse.model_validate(repo)
    )


@router.get("", response_model=APIResponse[List[RepositoryResponse]])
def list_repositories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all repositories owned by the current user."""
    repos = db.query(Repository).filter(Repository.user_id == current_user.id).order_by(Repository.created_at.desc()).all()
    return APIResponse(
        success=True,
        message="Repositories retrieved",
        data=[RepositoryResponse.model_validate(r) for r in repos]
    )


@router.get("/{repository_id}", response_model=APIResponse[RepositoryResponse])
def get_repository(repo: Repository = Depends(get_user_repository)):
    """Get repository metadata by ID."""
    return APIResponse(
        success=True,
        message="Repository retrieved",
        data=RepositoryResponse.model_validate(repo)
    )


@router.delete("/{repository_id}", response_model=APIResponse[dict])
def delete_repository(
    repo: Repository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """Delete repository, purging database records and storage."""
    RepositoryService.delete_repository(db, repo)
    return APIResponse(success=True, message=f"Repository '{repo.name}' deleted successfully", data={})


@router.post("/{repository_id}/index", response_model=APIResponse[dict], status_code=status.HTTP_202_ACCEPTED)
@router.post("/{repository_id}/reindex", response_model=APIResponse[dict])
def reindex_repository(
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """Trigger repository indexing / reindexing in the background."""
    job = IngestionJob(
        repository_id=repo.id,
        status="pending",
        progress=0,
        current_stage="queued"
    )
    db.add(job)
    repo.status = "pending"
    db.commit()

    background_tasks.add_task(process_repository_ingestion, repo.id, None)
    return APIResponse(success=True, message="Repository indexing queued successfully", data={"job_id": job.id, "repository_id": repo.id})


@router.get("/{repository_id}/index-status", response_model=APIResponse[RepositoryStatusResponse])
@router.get("/{repository_id}/status", response_model=APIResponse[RepositoryStatusResponse])
def get_repository_status(
    repo: Repository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """Get latest indexing status and progress."""
    latest_job = db.query(IngestionJob).filter(
        IngestionJob.repository_id == repo.id
    ).order_by(IngestionJob.started_at.desc()).first()

    progress = latest_job.progress if latest_job else (100 if repo.status == "ready" else 0)
    current_stage = latest_job.current_stage if latest_job else ("ready" if repo.status == "ready" else "idle")

    return APIResponse(
        success=True,
        message="Status retrieved",
        data=RepositoryStatusResponse(
            id=repo.id,
            status=repo.status,
            progress=progress,
            current_stage=current_stage,
            error_message=repo.error_message,
            total_files=repo.total_files,
            total_chunks=repo.total_chunks,
            last_indexed_at=repo.last_indexed_at
        )
    )


@router.get("/{repository_id}/files", response_model=APIResponse[List[RepositoryFileItem]])
def list_repository_files(
    repo: Repository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """List indexed files for repository tree navigation."""
    files = db.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).order_by(RepositoryFile.file_path).all()
    return APIResponse(
        success=True,
        message="Files retrieved",
        data=[RepositoryFileItem.model_validate(f) for f in files]
    )


@router.get("/{repository_id}/file-content", response_model=APIResponse[FileContentResponse])
def get_file_content(
    path: str,
    repo: Repository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """Get file content for Monaco Editor display."""
    content, language, line_count, file_size = RepositoryService.get_file_content(db, repo.id, path)
    return APIResponse(
        success=True,
        message="File content retrieved",
        data=FileContentResponse(
            file_path=path,
            language=language,
            content=content,
            total_lines=line_count,
            file_size=file_size
        )
    )
