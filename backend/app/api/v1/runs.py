from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.agent_run import AgentRun
from app.models.tool_execution import ToolExecution
from app.models.patch import Patch
from app.schemas.run import AgentRunResponse, ToolExecutionResponse
from app.schemas.common import APIResponse

router = APIRouter(prefix="/runs", tags=["Agent Runs & Tool Executions"])


@router.get("/{run_id}", response_model=APIResponse[AgentRunResponse])
def get_agent_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve execution status and findings of an AI debugging run."""
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this run.")

    patches = db.query(Patch).filter(Patch.agent_run_id == run.id).all()
    patch_ids = [p.id for p in patches]

    return APIResponse(
        success=True,
        message="Agent run retrieved",
        data=AgentRunResponse(
            id=run.id,
            repository_id=run.repository_id,
            issue_id=run.issue_id,
            user_id=run.user_id,
            status=run.status,
            current_step=run.current_step,
            iterations=run.iterations,
            query=run.query,
            root_cause_analysis=run.root_cause_analysis,
            proposed_fix_summary=run.proposed_fix_summary,
            generated_tests=run.generated_tests,
            error_message=run.error_message,
            execution_log=run.execution_log,
            created_at=run.created_at,
            completed_at=run.completed_at,
            patch_ids=patch_ids
        )
    )


@router.get("/{run_id}/tools", response_model=APIResponse[List[ToolExecutionResponse]])
def get_run_tool_executions(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve full tool execution history for a debugging run."""
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this run.")

    tools = db.query(ToolExecution).filter(
        ToolExecution.agent_run_id == run_id
    ).order_by(ToolExecution.created_at.asc()).all()

    return APIResponse(
        success=True,
        message="Tool execution history retrieved",
        data=[
            ToolExecutionResponse(
                id=t.id,
                agent_run_id=t.agent_run_id,
                tool_name=t.tool_name,
                arguments=t.arguments,
                result=t.result,
                status=t.status,
                execution_time_ms=t.execution_time_ms,
                created_at=t.created_at
            )
            for t in tools
        ]
    )
