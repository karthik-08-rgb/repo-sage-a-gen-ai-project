import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, in_progress, completed, failed
    progress = Column(Integer, default=0, nullable=False)  # 0 to 100 percentage
    current_stage = Column(String(100), default="queued", nullable=False)  # discovery, parsing, chunking, embedding, indexing, ready
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    repository = relationship("Repository", back_populates="ingestion_jobs")
