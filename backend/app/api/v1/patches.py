import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.patch import Patch
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.agent_run import AgentRun
from app.schemas.patch import PatchResponse, PatchDiffResponse, PatchApprovalResponse
from app.schemas.common import APIResponse
from app.services.code_generation.code_suggester import apply_unified_diff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patches", tags=["Patches & Human Approval"])


@router.get("/{patch_id}", response_model=APIResponse[PatchResponse])
def get_patch_details(
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get metadata and status of a proposed code patch."""
    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patch '{patch_id}' not found.")
    if patch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this patch.")

    return APIResponse(
        success=True,
        message="Patch retrieved",
        data=PatchResponse.model_validate(patch)
    )


@router.get("/{patch_id}/diff", response_model=APIResponse[PatchDiffResponse])
def get_patch_diff(
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unified git diff for human review with line change counts."""
    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patch '{patch_id}' not found.")
    if patch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this patch.")

    diff_lines = patch.unified_diff.splitlines()
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    return APIResponse(
        success=True,
        message="Patch diff retrieved",
        data=PatchDiffResponse(
            patch_id=patch.id,
            target_file=patch.target_file,
            unified_diff=patch.unified_diff,
            added_lines=added,
            removed_lines=removed
        )
    )


@router.post("/{patch_id}/approve", response_model=APIResponse[PatchApprovalResponse])
def approve_patch(
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explicit Human Approval workflow:
    1. Validates repository workspace state and target file path.
    2. Enforces path traversal security checks.
    3. Safely applies unified git diff to the repository workspace file.
    4. Records approval and application timestamps.
    5. Updates AgentRun state to completed.
    """
    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patch '{patch_id}' not found.")
    if patch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this patch.")

    if patch.status == "applied":
        return APIResponse(
            success=True,
            message="Patch has already been applied.",
            data=PatchApprovalResponse(
                patch_id=patch.id,
                status=patch.status,
                applied_to_file=patch.target_file,
                message="Already applied.",
                approved_at=patch.approved_at or datetime.now(timezone.utc)
            )
        )

    repo = db.query(Repository).filter(Repository.id == patch.repository_id).first()
    if not repo or not repo.local_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository workspace not found.")

    base_dir = Path(repo.local_path).resolve()
    target_file = (base_dir / patch.target_file).resolve()

    # Path traversal protection
    try:
        target_file.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Target file path escapes repository root."
        )

    # Apply diff
    try:
        if target_file.is_file():
            original_content = target_file.read_text(encoding="utf-8", errors="replace")
            new_content = apply_unified_diff(original_content, patch.unified_diff)
            target_file.write_text(new_content, encoding="utf-8")
        else:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            added_lines = [
                l[1:] for l in patch.unified_diff.splitlines(keepends=True)
                if l.startswith("+") and not l.startswith("+++")
            ]
            new_content = "".join(added_lines)
            target_file.write_text(new_content, encoding="utf-8")
    except Exception as apply_err:
        logger.exception(f"Failed to apply approved patch: {apply_err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to apply patch: {apply_err}")

    # Update patch record
    now = datetime.now(timezone.utc)
    patch.status = "applied"
    patch.approved_at = now
    patch.applied_at = now

    # Update agent run status if linked
    if patch.agent_run_id:
        run = db.query(AgentRun).filter(AgentRun.id == patch.agent_run_id).first()
        if run:
            run.status = "completed"
            run.completed_at = now

    # Update file size in repository files
    rf = db.query(RepositoryFile).filter(
        RepositoryFile.repository_id == patch.repository_id,
        RepositoryFile.file_path == patch.target_file
    ).first()
    if rf:
        rf.file_size = len(new_content.encode("utf-8"))

    db.commit()

    return APIResponse(
        success=True,
        message=f"Patch approved and cleanly applied to '{patch.target_file}'.",
        data=PatchApprovalResponse(
            patch_id=patch.id,
            status="applied",
            applied_to_file=patch.target_file,
            message="Patch successfully verified and applied to workspace file.",
            approved_at=now
        )
    )


@router.post("/{patch_id}/reject", response_model=APIResponse[PatchResponse])
def reject_patch(
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Explicitly reject a proposed code patch."""
    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patch '{patch_id}' not found.")
    if patch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this patch.")

    now = datetime.now(timezone.utc)
    patch.status = "rejected"
    patch.rejected_at = now

    if patch.agent_run_id:
        run = db.query(AgentRun).filter(AgentRun.id == patch.agent_run_id).first()
        if run:
            run.status = "rejected"
            run.completed_at = now

    db.commit()
    db.refresh(patch)

    return APIResponse(
        success=True,
        message="Patch marked as rejected",
        data=PatchResponse.model_validate(patch)
    )
