from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.models.code_change import CodeChange
from app.schemas.code import CodeSuggestRequest, CodeSuggestResponse, ApplyDiffRequest, DiffChangeResponse
from app.schemas.common import APIResponse
from app.services.code_generation.code_suggester import CodeSuggesterService

router = APIRouter(prefix="/code", tags=["AI Code Suggestions & Patches"])


@router.post("/suggest", response_model=APIResponse[CodeSuggestResponse])
def suggest_code_modification(
    req: CodeSuggestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Propose code improvements and unified diff for human review."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    suggester = CodeSuggesterService(db, req.repository_id)
    response = suggester.generate_suggestion(req, current_user)

    return APIResponse(
        success=True,
        message="Code suggestion generated for review",
        data=response
    )


@router.post("/apply-approved-diff", response_model=APIResponse[DiffChangeResponse])
def apply_approved_diff(
    req: ApplyDiffRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Explicit human approval step: validates target files and applies approved diff."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    suggester = CodeSuggesterService(db, req.repository_id)
    if req.change_id:
        applied = suggester.apply_approved_change(req.change_id, current_user, target_path_override=req.file_path)
    elif req.unified_diff and req.file_path:
        applied = suggester.apply_diff_direct(req.file_path, req.unified_diff, current_user)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either change_id or file_path + unified_diff is required.")

    return APIResponse(
        success=True,
        message="Diff approved and applied to repository workspace.",
        data=DiffChangeResponse.model_validate(applied)
    )


@router.get("/diff/{change_id}", response_model=APIResponse[DiffChangeResponse])
def get_diff_change(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get metadata and patch content of a proposed code change."""
    change = db.query(CodeChange).filter(
        CodeChange.id == change_id,
        CodeChange.user_id == current_user.id
    ).first()
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change not found.")

    return APIResponse(
        success=True,
        message="Code change retrieved",
        data=DiffChangeResponse.model_validate(change)
    )
