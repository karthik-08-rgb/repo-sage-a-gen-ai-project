from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CitationItem(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None


class ChatSessionCreate(BaseModel):
    repository_id: str
    title: Optional[str] = "New Conversation"


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    repository_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    repository_id: str
    session_id: Optional[str] = None
    question: str = Field(min_length=1, description="Question about the repository code")
    history_limit: Optional[int] = 10


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    citations: List[CitationItem] = []
    model: Optional[str] = None
    token_usage: Optional[dict] = None
    created_at: datetime


class GroundedAnswerPayload(BaseModel):
    direct_answer: str
    explanation: str
    relevant_files: List[str]
    citations: List[CitationItem]
    dependencies_or_flow: Optional[str] = None
    confidence_limitations: Optional[str] = None


class AgentWorkflowRequest(BaseModel):
    repository_id: str
    query: str = Field(min_length=1, description="Agent query or goal")
    session_id: Optional[str] = None


class AgentWorkflowResponse(BaseModel):
    repository_id: str
    intent: str
    detected_language: Optional[str] = None
    extracted_symbols: List[str] = []
    extracted_files: List[str] = []
    direct_answer: str
    explanation: Optional[str] = None
    execution_flow: Optional[str] = None
    citations: List[CitationItem] = []
    execution_log: List[str] = []
    session_id: Optional[str] = None
