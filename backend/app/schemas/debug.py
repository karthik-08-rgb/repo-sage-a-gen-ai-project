from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.chat import CitationItem


class DebugAnalyzeRequest(BaseModel):
    repository_id: str
    error_message: str = Field(min_length=1, description="Error message or exception string")
    stack_trace: Optional[str] = Field(default="", description="Full stack trace if available")
    relevant_file: Optional[str] = Field(default=None, description="Optional target file path")
    expected_behavior: Optional[str] = Field(default=None, description="What was expected to happen")


class SuggestedFixItem(BaseModel):
    file_path: str
    description: str
    unified_diff: str
    validation_steps: List[str]
    confidence: str  # High, Medium, Low


class DebugAnalyzeResponse(BaseModel):
    run_id: Optional[str] = None
    patch_id: Optional[str] = None
    error_summary: str
    potential_root_cause: str
    evidence_from_codebase: str
    affected_files: List[str]
    citations: List[CitationItem]
    suggested_fixes: List[SuggestedFixItem]
    tests_to_validate: List[str]
    generated_tests: Optional[str] = None
    confidence_limitations: str
