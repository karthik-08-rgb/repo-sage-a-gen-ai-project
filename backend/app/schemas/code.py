from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CodeSuggestRequest(BaseModel):
    repository_id: str
    file_path: str
    instruction: str = Field(min_length=1, description="Refactoring, bugfix, or feature instruction")
    context_lines: Optional[str] = None


class CodeSuggestResponse(BaseModel):
    repository_id: str
    file_path: str
    instruction: str
    explanation: str
    unified_diff: str
    original_code: str
    suggested_code: str
    change_id: Optional[str] = None


class ApplyDiffRequest(BaseModel):
    repository_id: str
    file_path: str
    unified_diff: str
    change_id: Optional[str] = None


class DiffChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    user_id: str
    status: str  # pending_review, approved, applied, rejected
    patch_content: str
    created_at: datetime
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
