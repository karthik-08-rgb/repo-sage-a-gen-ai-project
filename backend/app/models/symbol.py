import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    file_id = Column(String(36), ForeignKey("repository_files.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(255), index=True, nullable=False)
    symbol_type = Column(String(100), index=True, nullable=False)  # class, method, function, interface, struct, etc.
    parent_name = Column(String(255), nullable=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    docstring = Column(Text, nullable=True)
    decorators_json = Column(Text, nullable=True)
    dependencies_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="symbols")
    file = relationship("RepositoryFile", back_populates="symbols")

    @property
    def decorators(self) -> List[str]:
        if self.decorators_json:
            try:
                return json.loads(self.decorators_json)
            except Exception:
                return []
        return []

    @decorators.setter
    def decorators(self, val: List[str]):
        self.decorators_json = json.dumps(val) if val else "[]"

    @property
    def dependencies(self) -> List[str]:
        if self.dependencies_json:
            try:
                return json.loads(self.dependencies_json)
            except Exception:
                return []
        return []

    @dependencies.setter
    def dependencies(self, val: List[str]):
        self.dependencies_json = json.dumps(val) if val else "[]"
