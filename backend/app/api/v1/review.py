from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.schemas.review import CodeReviewRequest, CodeReviewResponse
from app.schemas.common import APIResponse
from app.services.code_review.reviewer import CodeReviewService

router = APIRouter(prefix="/review", tags=["AI Code Review"])


@router.post("", response_model=APIResponse[CodeReviewResponse])
def review_code(
    req: CodeReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run an automated multi-factor code review evaluating bugs, security, and performance."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    reviewer = CodeReviewService(db, req.repository_id)
    review_res = reviewer.review_code(req)

    return APIResponse(
        success=True,
        message="Code review completed",
        data=review_res
    )
