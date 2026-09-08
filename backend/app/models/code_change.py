import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class CodeChange(Base):
    __tablename__ = "code_changes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    original_commit_sha = Column(String(100), nullable=True)
    patch_content = Column(Text, nullable=False)  # Unified git diff
    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, approved, applied, rejected
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)

    repository = relationship("Repository", back_populates="code_changes")
    user = relationship("User", back_populates="code_changes")
