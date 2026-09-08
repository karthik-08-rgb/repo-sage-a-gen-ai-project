import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

# Try importing pgvector Vector type if available
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    file_id = Column(String(36), ForeignKey("repository_files.id", ondelete="CASCADE"), index=True, nullable=False)
    content = Column(Text, nullable=False)
    symbol_name = Column(String(255), nullable=True, index=True)
    symbol_type = Column(String(100), nullable=True, index=True)  # function, class, method, module, block
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    language = Column(String(100), nullable=True)
    
    # Embedding stored as JSON serialized float list for portability across SQLite and PostgreSQL
    # In PostgreSQL with pgvector, an embedding vector column or indexing can be maintained
    embedding_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="chunks")
    file = relationship("RepositoryFile", back_populates="chunks")

    @property
    def embedding(self) -> Optional[List[float]]:
        if self.embedding_json:
            try:
                return json.loads(self.embedding_json)
            except Exception:
                return None
        return None

    @embedding.setter
    def embedding(self, val: Optional[List[float]]):
        if val is not None:
            self.embedding_json = json.dumps(val)
        else:
            self.embedding_json = None

    @property
    def chunk_metadata(self) -> dict:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except Exception:
                return {}
        return {}

    @chunk_metadata.setter
    def chunk_metadata(self, val: dict):
        self.metadata_json = json.dumps(val) if val else "{}"
