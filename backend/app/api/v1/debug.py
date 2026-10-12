from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.schemas.debug import DebugAnalyzeRequest, DebugAnalyzeResponse
from app.schemas.common import APIResponse
from app.services.debugging.debugger import DebuggerService

router = APIRouter(prefix="/debug", tags=["AI Debugging Assistant"])


@router.post("", response_model=APIResponse[DebugAnalyzeResponse])
@router.post("/analyze", response_model=APIResponse[DebugAnalyzeResponse])
def analyze_error(
    req: DebugAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze stack trace and error message using LangGraph to identify root cause and propose unified diff fix."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if cast(str, repo.user_id) != cast(str, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    debugger = DebuggerService(db, req.repository_id)
    response = debugger.analyze_error(req, user_id=cast(str, current_user.id))

    return APIResponse(
        success=True,
        message="Debug analysis complete",
        data=response
    )
