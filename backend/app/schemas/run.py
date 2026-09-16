from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ToolExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_run_id: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    status: str
    execution_time_ms: int
    created_at: datetime


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    issue_id: Optional[str] = None
    user_id: str
    status: str
    current_step: str
    iterations: int
    query: str
    root_cause_analysis: Optional[str] = None
    proposed_fix_summary: Optional[str] = None
    generated_tests: Optional[str] = None
    error_message: Optional[str] = None
    execution_log: List[str] = []
    created_at: datetime
    completed_at: Optional[datetime] = None
    patch_ids: List[str] = []
