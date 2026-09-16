from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class RepositoryCreateGitHub(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Human-readable name")
    url: str = Field(description="Public or private GitHub repository URL")
    branch: Optional[str] = Field(default="main", description="Target Git branch")
    access_token: Optional[str] = Field(default=None, description="Optional scoped PAT for private repos")


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    source_type: str
    source_url: Optional[str]
    default_branch: str
    commit_sha: Optional[str]
    primary_language: Optional[str]
    status: str
    total_files: int
    total_chunks: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_indexed_at: Optional[datetime]


class RepositoryStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    current_stage: str
    error_message: Optional[str] = None
    total_files: int
    total_chunks: int
    last_indexed_at: Optional[datetime] = None


class RepositoryFileItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_path: str
    language: Optional[str]
    file_size: int
    indexed_at: datetime


class FileContentResponse(BaseModel):
    file_path: str
    language: Optional[str]
    content: str
    total_lines: int
    file_size: int
