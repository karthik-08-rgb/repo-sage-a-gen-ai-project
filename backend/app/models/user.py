import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    repositories = relationship("Repository", back_populates="owner", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    code_changes = relationship("CodeChange", back_populates="user", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="user", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="user", cascade="all, delete-orphan")
    patches = relationship("Patch", back_populates="user", cascade="all, delete-orphan")
