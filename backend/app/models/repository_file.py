import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    file_path = Column(String(1024), nullable=False, index=True)
    language = Column(String(100), nullable=True)
    content_hash = Column(String(64), nullable=True)
    file_size = Column(Integer, default=0, nullable=False)
    indexed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")
    symbols = relationship("Symbol", back_populates="file", cascade="all, delete-orphan")
