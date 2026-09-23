import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from git import Repo, GitCommandError
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.ingestion_job import IngestionJob
from app.models.user import User
from app.core.config import settings
from app.core.exceptions import RepoSageException, EntityNotFoundException
from app.services.repository.security_validator import validate_repository_url
from app.services.repository.zip_validator import extract_zip_safely

logger = logging.getLogger(__name__)


class RepositoryService:
    @staticmethod
    def get_repo_dir(repository_id: str) -> Path:
        base_dir = Path(settings.REPO_STORAGE_PATH).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / repository_id

    @classmethod
    def create_github_repo(
        cls,
        db: Session,
        user: User,
        name: str,
        url: str,
        branch: str = "main",
        access_token: Optional[str] = None
    ) -> Repository:
        """Create a new GitHub-backed repository record and schedule ingestion."""
        validated_url = validate_repository_url(url)

        # Check for existing repository registration to prevent duplicates
        existing = db.query(Repository).filter(
            Repository.user_id == user.id,
            Repository.source_url == validated_url
        ).first()
        if existing:
            logger.info(f"Repository {validated_url} already registered as ID {existing.id}")
            return existing

        repo = Repository(
            user_id=user.id,
            name=name.strip(),
            source_type="github_private" if access_token else "github_public",
            source_url=validated_url,
            default_branch=branch.strip() or "main",
            status="pending"
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

        repo_dir = cls.get_repo_dir(repo.id)
        repo.local_path = str(repo_dir)

        # Create initial ingestion job
        job = IngestionJob(
            repository_id=repo.id,
            status="pending",
            progress=0,
            current_stage="queued"
        )
        db.add(job)
        db.commit()
        db.refresh(repo)
        return repo

    @classmethod
    def create_zip_repo(
        cls,
        db: Session,
        user: User,
        name: str,
        zip_tmp_path: str
    ) -> Repository:
        """Create a new repository from an uploaded ZIP archive."""
        repo = Repository(
            user_id=user.id,
            name=name.strip(),
            source_type="zip",
            source_url=None,
            default_branch="main",
            status="pending"
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

        repo_dir = cls.get_repo_dir(repo.id)
        repo.local_path = str(repo_dir)

        try:
            extracted_count = extract_zip_safely(zip_tmp_path, str(repo_dir))
            logger.info(f"Extracted {extracted_count} files for repo {repo.id}")
        except Exception as e:
            repo.status = "failed"
            repo.error_message = f"ZIP extraction failed: {str(e)}"
            db.commit()
            raise RepoSageException(f"Failed to extract repository archive: {str(e)}")

        job = IngestionJob(
            repository_id=repo.id,
            status="pending",
            progress=10,
            current_stage="extracted"
        )
        db.add(job)
        db.commit()
        db.refresh(repo)
        return repo

    @classmethod
    def clone_repository(cls, repo: Repository, access_token: Optional[str] = None) -> str:
        """Clone Git repository to local storage with depth 1."""
        dest = Path(repo.local_path)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)

        clone_url = repo.source_url
        if access_token and clone_url.startswith("https://"):
            # Insert token into clone url safely in-memory only
            clone_url = clone_url.replace("https://", f"https://x-access-token:{access_token}@")

        try:
            logger.info(f"Cloning {repo.source_url} branch {repo.default_branch} into {dest}")
            git_repo = Repo.clone_from(
                clone_url,
                str(dest),
                branch=repo.default_branch,
                depth=1,
                kill_after_timeout=60
            )
            head_commit = git_repo.head.commit.hexsha
            return head_commit
        except GitCommandError as e:
            logger.error(f"Git clone error: {e.stderr}")
            raise RepoSageException(f"Git clone failed: {e.stderr or str(e)}")

    @classmethod
    def delete_repository(cls, db: Session, repo: Repository) -> None:
        """Delete repository database records and purge storage and vectors."""
        try:
            from app.services.retrieval.qdrant_service import get_qdrant_service
            get_qdrant_service().delete_repository_vectors(repo.id)
        except Exception as e:
            logger.warning(f"Could not purge Qdrant vectors for repo {repo.id}: {e}")

        if repo.local_path and os.path.exists(repo.local_path):
            shutil.rmtree(repo.local_path, ignore_errors=True)

        db.delete(repo)
        db.commit()

    @staticmethod
    def get_file_content(db: Session, repository_id: str, file_path: str) -> Tuple[str, str, int, int]:
        """Safely fetch file content from repository local workspace."""
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo or not repo.local_path:
            raise EntityNotFoundException("Repository", repository_id)

        base_dir = Path(repo.local_path).resolve()
        target_file = (base_dir / file_path).resolve()

        # Path traversal guard using is_relative_to
        try:
            target_file.relative_to(base_dir)
        except ValueError:
            raise RepoSageException("Access denied: Path attempts to escape repository workspace.")

        if not target_file.is_file():
            raise EntityNotFoundException("File", file_path)

        # File size check
        stat = target_file.stat()
        if stat.st_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise RepoSageException(f"File size ({stat.st_size} bytes) exceeds limit of {settings.MAX_FILE_SIZE_MB}MB.")

        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            raise RepoSageException(f"Failed to read file content: {str(e)}")

        lines = content.splitlines()
        suffix = target_file.suffix.lstrip(".").lower()
        return content, suffix, len(lines), stat.st_size
