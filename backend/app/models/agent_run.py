import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    issue_id = Column(String(36), ForeignKey("issues.id", ondelete="SET NULL"), index=True, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status = Column(String(50), default="running", nullable=False)  # running, completed, failed, awaiting_approval
    current_step = Column(String(100), default="started", nullable=False)
    iterations = Column(Integer, default=0, nullable=False)
    query = Column(Text, nullable=False)
    root_cause_analysis = Column(Text, nullable=True)
    proposed_fix_summary = Column(Text, nullable=True)
    generated_tests = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_log_json = Column(Text, nullable=True)
    token_usage_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    repository = relationship("Repository", back_populates="agent_runs")
    issue = relationship("Issue", back_populates="agent_runs")
    user = relationship("User", back_populates="agent_runs")
    tool_executions = relationship("ToolExecution", back_populates="agent_run", cascade="all, delete-orphan", order_by="ToolExecution.created_at")
    patches = relationship("Patch", back_populates="agent_run")

    @property
    def execution_log(self) -> List[str]:
        if self.execution_log_json:
            try:
                return json.loads(self.execution_log_json)
            except Exception:
                return []
        return []

    @execution_log.setter
    def execution_log(self, val: List[str]):
        self.execution_log_json = json.dumps(val) if val else "[]"

    @property
    def token_usage(self) -> Dict[str, Any]:
        if self.token_usage_json:
            try:
                return json.loads(self.token_usage_json)
            except Exception:
                return {}
        return {}

    @token_usage.setter
    def token_usage(self, val: Dict[str, Any]):
        self.token_usage_json = json.dumps(val) if val else "{}"
