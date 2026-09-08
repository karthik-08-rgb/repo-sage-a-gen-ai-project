import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # github_public, github_private, zip
    source_url = Column(String(512), nullable=True)
    default_branch = Column(String(100), default="main", nullable=False)
    commit_sha = Column(String(100), nullable=True)
    primary_language = Column(String(100), nullable=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, cloning, indexing, ready, failed
    total_files = Column(Integer, default=0, nullable=False)
    total_chunks = Column(Integer, default=0, nullable=False)
    local_path = Column(String(1024), nullable=True)  # Storage path on server
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_indexed_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="repositories")
    files = relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")
    chunks = relationship("CodeChunk", back_populates="repository", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="repository", cascade="all, delete-orphan")
    ingestion_jobs = relationship("IngestionJob", back_populates="repository", cascade="all, delete-orphan")
    code_changes = relationship("CodeChange", back_populates="repository", cascade="all, delete-orphan")
    symbols = relationship("Symbol", back_populates="repository", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="repository", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="repository", cascade="all, delete-orphan")
    patches = relationship("Patch", back_populates="repository", cascade="all, delete-orphan")
