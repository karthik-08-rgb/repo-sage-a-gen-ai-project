from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    status: str
    progress: int
    current_stage: str
    error_message: Optional[str] = None
    retry_count: int
    started_at: datetime
    completed_at: Optional[datetime] = None
