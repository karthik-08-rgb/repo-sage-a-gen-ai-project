from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    CitationItem,
    AgentWorkflowRequest,
    AgentWorkflowResponse,
)
from app.schemas.common import APIResponse
from app.services.rag.rag_service import RAGService
from app.services.rag.llm_provider import get_llm_provider
from app.services.retrieval.retriever import HybridRetriever
from app.agents.workflow import RepoSageWorkflow

router = APIRouter(prefix="/chat", tags=["Codebase Chat & RAG"])


@router.post("", response_model=APIResponse[ChatMessageResponse])
def send_chat_message(
    req: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ask a question about the repository with grounded retrieval and verified citations."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    rag_service = RAGService(db, req.repository_id)
    assistant_msg, session = rag_service.answer_question(
        question=req.question,
        user=current_user,
        session_id=req.session_id
    )

    # Convert citations back to schema
    citations_data = [CitationItem(**c) for c in (assistant_msg.citations or [])]

    return APIResponse(
        success=True,
        message="Answer generated",
        data=ChatMessageResponse(
            id=assistant_msg.id,
            session_id=session.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            citations=citations_data,
            model=assistant_msg.model,
            token_usage=assistant_msg.token_usage,
            created_at=assistant_msg.created_at
        )
    )


@router.post("/agent", response_model=APIResponse[AgentWorkflowResponse])
def run_agent_workflow(
    req: AgentWorkflowRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run full multi-step agent workflow: intent understanding, retrieval, AST analysis, citation check."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    workflow = RepoSageWorkflow(db, req.repository_id)
    state = workflow.run(req.query)

    direct_ans = state.answer_payload.direct_answer if state.answer_payload else "Completed agent analysis."
    explanation = state.answer_payload.explanation if state.answer_payload else ""
    flow = state.answer_payload.dependencies_or_flow if state.answer_payload else None

    # Persist in chat session if session_id provided or create session
    session = None
    if req.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == req.session_id,
            ChatSession.user_id == current_user.id
        ).first()

    if not session:
        session = ChatSession(
            user_id=current_user.id,
            repository_id=req.repository_id,
            title=f"[Agent] {req.query.strip()[:50]}"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Save user message
    db.add(ChatMessage(session_id=session.id, role="user", content=req.query))

    # Save assistant message
    asst_content = f"### Agent Analysis ({state.intent})\n{direct_ans}"
    if explanation:
        asst_content += f"\n\n### Details\n{explanation}"
    if flow:
        asst_content += f"\n\n### Flow & Dependencies\n{flow}"

    asst_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=asst_content,
        model="reposage-agent-v1"
    )
    asst_msg.citations = [c.model_dump() for c in state.validated_citations]
    db.add(asst_msg)
    db.commit()

    return APIResponse(
        success=True,
        message="Agent workflow executed successfully",
        data=AgentWorkflowResponse(
            repository_id=req.repository_id,
            intent=state.intent,
            detected_language=state.detected_language,
            extracted_symbols=state.extracted_symbols,
            extracted_files=state.extracted_files,
            direct_answer=direct_ans,
            explanation=explanation,
            execution_flow=flow,
            citations=state.validated_citations,
            execution_log=state.execution_log,
            session_id=session.id
        )
    )


@router.post("/stream")
def stream_chat_message(
    req: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stream response tokens using Server-Sent Events (SSE)."""
    import json
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    retriever = HybridRetriever(db, req.repository_id)
    chunks = retriever.search(query=req.question, search_type="hybrid", top_k=6)

    context_snippets = []
    for i, rc in enumerate(chunks, start=1):
        context_snippets.append(
            f"[Chunk {i}] {rc.file_path} (Lines {rc.start_line}-{rc.end_line})\n```\n{rc.content}\n```"
        )
    context_str = "\n\n".join(context_snippets)

    system_prompt = (
        "You are RepoSage. Answer the developer's question grounded strictly in the provided codebase context. "
        "Cite confirmed file paths and line ranges."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion:\n{req.question}"}
    ]

    llm = get_llm_provider()

    def event_stream():
        citations_json = json.dumps([
            {"file_path": c.file_path, "start_line": c.start_line, "end_line": c.end_line, "symbol_name": c.symbol_name}
            for c in chunks[:3]
        ])
        yield f"event: citations\ndata: {citations_json}\n\n"

        for token in llm.stream(messages):
            data_token = json.dumps({"delta": token})
            yield f"data: {data_token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions", response_model=APIResponse[List[ChatSessionResponse]])
def list_chat_sessions(
    repository_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List chat conversation sessions for a repository."""
    sessions = db.query(ChatSession).filter(
        ChatSession.repository_id == repository_id,
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()

    return APIResponse(
        success=True,
        message="Sessions retrieved",
        data=[ChatSessionResponse.model_validate(s) for s in sessions]
    )


@router.get("/sessions/{session_id}", response_model=APIResponse[List[ChatMessageResponse]])
def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages in a chat session with citations."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()

    items = []
    for m in messages:
        cits = [CitationItem(**c) for c in (m.citations or [])]
        items.append(ChatMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            citations=cits,
            model=m.model,
            token_usage=m.token_usage,
            created_at=m.created_at
        ))

    return APIResponse(
        success=True,
        message="Messages retrieved",
        data=items
    )


@router.delete("/sessions/{session_id}", response_model=APIResponse[dict])
def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat conversation."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    db.delete(session)
    db.commit()
    return APIResponse(success=True, message="Session deleted", data={})
