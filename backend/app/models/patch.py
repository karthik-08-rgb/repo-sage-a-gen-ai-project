import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Patch(Base):
    __tablename__ = "patches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_run_id = Column(String(36), ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    issue_id = Column(String(36), ForeignKey("issues.id", ondelete="SET NULL"), index=True, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    target_file = Column(String(1024), nullable=False)
    unified_diff = Column(Text, nullable=False)
    original_commit_sha = Column(String(100), nullable=True)
    status = Column(String(50), default="pending_approval", nullable=False)  # pending_approval, approved, applied, rejected
    description = Column(Text, nullable=True)
    tests_passed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    repository = relationship("Repository", back_populates="patches")
    agent_run = relationship("AgentRun", back_populates="patches")
    issue = relationship("Issue", back_populates="patches")
    user = relationship("User", back_populates="patches")
