import logging
from typing import Optional
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.repository import Repository
from app.models.ingestion_job import IngestionJob
from app.services.repository.repo_service import RepositoryService
from app.services.ingestion.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


def process_repository_ingestion(repository_id: str, access_token: Optional[str] = None) -> None:
    """Core ingestion logic executed by Celery worker or FastAPI BackgroundTasks."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            logger.error(f"Repository {repository_id} not found for ingestion.")
            return

        job = db.query(IngestionJob).filter(
            IngestionJob.repository_id == repository_id
        ).order_by(IngestionJob.started_at.desc()).first()

        # If repo is a GitHub source and has not been cloned yet, clone it first
        if repo.source_type in ("github_public", "github_private") and repo.status == "pending":
            if job:
                job.current_stage = "cloning"
                job.progress = 10
                db.commit()

            commit_sha = RepositoryService.clone_repository(repo, access_token)
            repo.commit_sha = commit_sha
            db.commit()

        # Run full ingestion pipeline
        pipeline = IngestionPipeline(db, repo, job)
        files_indexed, chunks_indexed = pipeline.run()
        logger.info(f"Ingestion completed for {repo.name}: {files_indexed} files, {chunks_indexed} chunks.")

    except Exception as e:
        logger.exception(f"Error during repository ingestion task: {e}")
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.index_repository")
def index_repository_task(self, repository_id: str, access_token: Optional[str] = None):
    """Celery background task."""
    logger.info(f"Starting Celery indexing task {self.request.id} for repo {repository_id}")
    process_repository_ingestion(repository_id, access_token)
