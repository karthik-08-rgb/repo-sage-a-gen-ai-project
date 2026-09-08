import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Issue(Base):
    __tablename__ = "issues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    relevant_file = Column(String(1024), nullable=True)
    status = Column(String(50), default="open", nullable=False)  # open, investigating, resolved, closed
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="issues")
    user = relationship("User", back_populates="issues")
    agent_runs = relationship("AgentRun", back_populates="issue", cascade="all, delete-orphan")
    patches = relationship("Patch", back_populates="issue")
