import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=True)  # JSON-encoded list of citations
    model = Column(String(100), nullable=True)
    token_usage_json = Column(Text, nullable=True)  # JSON-encoded token usage stats
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("ChatSession", back_populates="messages")

    @property
    def citations(self) -> List[dict]:
        if self.citations_json:
            try:
                return json.loads(self.citations_json)
            except Exception:
                return []
        return []

    @citations.setter
    def citations(self, val: Optional[List[dict]]):
        if val is not None:
            self.citations_json = json.dumps(val)
        else:
            self.citations_json = None

    @property
    def token_usage(self) -> Optional[dict]:
        if self.token_usage_json:
            try:
                return json.loads(self.token_usage_json)
            except Exception:
                return None
        return None

    @token_usage.setter
    def token_usage(self, val: Optional[dict]):
        if val is not None:
            self.token_usage_json = json.dumps(val)
        else:
            self.token_usage_json = None
