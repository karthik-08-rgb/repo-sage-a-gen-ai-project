from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    agent_run_id: Optional[str] = None
    issue_id: Optional[str] = None
    user_id: str
    target_file: str
    unified_diff: str
    original_commit_sha: Optional[str] = None
    status: str  # pending_approval, approved, applied, rejected
    description: Optional[str] = None
    tests_passed: bool = False
    created_at: datetime
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


class PatchDiffResponse(BaseModel):
    patch_id: str
    target_file: str
    unified_diff: str
    added_lines: int
    removed_lines: int


class PatchApprovalResponse(BaseModel):
    patch_id: str
    status: str
    applied_to_file: str
    message: str
    approved_at: datetime
