import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_run_id = Column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    tool_name = Column(String(100), index=True, nullable=False)
    arguments_json = Column(Text, nullable=False, default="{}")
    result_json = Column(Text, nullable=False, default="{}")
    status = Column(String(50), default="success", nullable=False)  # success, failed
    execution_time_ms = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    agent_run = relationship("AgentRun", back_populates="tool_executions")

    @property
    def arguments(self) -> Dict[str, Any]:
        if self.arguments_json:
            try:
                return json.loads(self.arguments_json)
            except Exception:
                return {}
        return {}

    @arguments.setter
    def arguments(self, val: Dict[str, Any]):
        self.arguments_json = json.dumps(val) if val else "{}"

    @property
    def result(self) -> Any:
        if self.result_json:
            try:
                return json.loads(self.result_json)
            except Exception:
                return self.result_json
        return {}

    @result.setter
    def result(self, val: Any):
        if isinstance(val, (dict, list, str, int, float, bool)):
            self.result_json = json.dumps(val)
        else:
            self.result_json = str(val)
