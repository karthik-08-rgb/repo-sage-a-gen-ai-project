from typing import List, Optional
from pydantic import BaseModel, Field


class CodeReviewRequest(BaseModel):
    repository_id: str
    file_path: Optional[str] = Field(default=None, description="Path of file to review")
    code_snippet: Optional[str] = Field(default=None, description="Optional raw code snippet")


class ReviewFinding(BaseModel):
    title: str
    severity: str  # Critical, High, Medium, Low, Informational
    category: str  # Bug, Security, Performance, NullHandling, ExceptionHandling, Maintainability
    description: str
    evidence: str
    file_path: str
    start_line: int
    end_line: int
    suggested_improvement: str
    confidence: str  # High, Medium, Low


class CodeReviewResponse(BaseModel):
    repository_id: str
    target: str
    total_findings: int
    findings: List[ReviewFinding]
    summary: str
