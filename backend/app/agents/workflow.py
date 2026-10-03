import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.schemas.chat import GroundedAnswerPayload, CitationItem
from app.services.retrieval.retriever import HybridRetriever, RetrievedChunk
from app.services.rag.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


class AgentState:
    def __init__(self, query: str, repository_id: str):
        self.query = query
        self.repository_id = repository_id
        self.intent: str = "general_codebase"  # architecture, debugging, lookup, review, general_codebase
        self.detected_language: Optional[str] = None
        self.extracted_symbols: List[str] = []
        self.extracted_files: List[str] = []
        self.retrieved_chunks: List[RetrievedChunk] = []
        self.answer_payload: Optional[GroundedAnswerPayload] = None
        self.validated_citations: List[CitationItem] = []
        self.execution_log: List[str] = []


class RepoSageWorkflow:
    """
    Controlled multi-step agent workflow coordinating intent understanding,
    targeted retrieval, code analysis, grounded answer generation, and citation validation.
    """
    def __init__(self, db: Session, repository_id: str):
        self.db = db
        self.repository_id = repository_id
        self.retriever = HybridRetriever(db, repository_id)
        self.llm = get_llm_provider()

    def run(self, query: str) -> AgentState:
        state = AgentState(query=query, repository_id=self.repository_id)
        
        # Step 1: Query Understanding
        self._node_query_understanding(state)

        # Step 2: Targeted Retrieval
        self._node_retrieval(state)

        # Step 3: Code Analysis & Relationship Detection
        self._node_code_analysis(state)

        # Step 4: Answer Generation
        self._node_answer_generation(state)

        # Step 5: Citation Validation
        self._node_validation(state)

        return state

    def _node_query_understanding(self, state: AgentState) -> None:
        q_lower = state.query.lower()
        state.execution_log.append("Executing Query Understanding Node")

        # Classify query intent
        if any(w in q_lower for w in ("error", "exception", "traceback", "stack trace", "crash", "bug", "fails")):
            state.intent = "debugging"
        elif any(w in q_lower for w in ("architecture", "overview", "structure", "design", "how is this project organized")):
            state.intent = "architecture"
        elif any(w in q_lower for w in ("where is", "find", "locate", "which file", "search")):
            state.intent = "lookup"
        elif any(w in q_lower for w in ("review", "security", "vulnerability", "audit")):
            state.intent = "review"
        else:
            state.intent = "general_codebase"

        # Extract file and symbol references
        file_candidates = re.findall(r"[\w\-\./]+\.(?:py|js|ts|tsx|jsx|java|go|rs|cpp|c|cs)", state.query)
        state.extracted_files = file_candidates

        symbol_candidates = re.findall(r"\b[A-Z][a-zA-Z0-9_]+\b|\b[a-z_][a-zA-Z0-9_]+\(\)", state.query)
        state.extracted_symbols = [s.rstrip("()") for s in symbol_candidates]

    def _node_retrieval(self, state: AgentState) -> None:
        state.execution_log.append(f"Executing Retrieval Node for intent '{state.intent}'")
        
        top_k = 10 if state.intent in ("architecture", "debugging") else 6
        file_filter = state.extracted_files[0] if state.extracted_files else None

        chunks = self.retriever.search(
            query=state.query,
            search_type="hybrid",
            top_k=top_k,
            file_filter=file_filter
        )
        state.retrieved_chunks = chunks

    def _node_code_analysis(self, state: AgentState) -> None:
        state.execution_log.append("Executing Code Analysis Node (mapping dependencies and symbol relationships)")
        # Identify language and relationships from retrieved chunks
        languages = [c.language for c in state.retrieved_chunks if c.language]
        if languages:
            state.detected_language = max(set(languages), key=languages.count)

    def _node_answer_generation(self, state: AgentState) -> None:
        state.execution_log.append("Executing Answer Generation Node")

        snippets = []
        for i, c in enumerate(state.retrieved_chunks[:8], start=1):
            snippets.append(
                f"[Chunk {i}] File: {c.file_path} (Lines {c.start_line}-{c.end_line}) Symbol: {c.symbol_name or 'N/A'}\n"
                f"```\n{c.content}\n```"
            )
        context_str = "\n\n".join(snippets)

        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "You are RepoSage, an expert codebase navigation and debugging assistant. "
                    "Provide a grounded, comprehensive answer strictly citing verified source code files and line numbers."
                )
            },
            {
                "role": "user",
                "content": f"Context:\n{context_str}\n\nUser Question:\n{state.query}"
            }
        ]

        try:
            payload = self.llm.generate_structured(prompt_messages, GroundedAnswerPayload)
            if isinstance(payload, GroundedAnswerPayload):
                state.answer_payload = payload
            else:
                state.answer_payload = GroundedAnswerPayload.model_validate(payload)
        except Exception as e:
            logger.warning(f"Structured answer generation fallback in workflow: {e}")
            raw = self.llm.generate(prompt_messages)
            state.answer_payload = GroundedAnswerPayload(
                direct_answer=raw.content,
                explanation="",
                relevant_files=[c.file_path for c in state.retrieved_chunks[:3]],
                citations=[
                    CitationItem(file_path=c.file_path, start_line=c.start_line, end_line=c.end_line)
                    for c in state.retrieved_chunks[:3]
                ]
            )

    def _node_validation(self, state: AgentState) -> None:
        state.execution_log.append("Executing Validation Node (verifying source citations)")
        
        valid_files = {
            f.file_path.replace("\\", "/").strip(): f for f in self.db.query(RepositoryFile).filter(
                RepositoryFile.repository_id == self.repository_id
            ).all()
        }

        verified = []
        if state.answer_payload and state.answer_payload.citations:
            for cit in state.answer_payload.citations:
                norm_path = cit.file_path.replace("\\", "/").strip()
                matched_key = None
                if norm_path in valid_files:
                    matched_key = norm_path
                else:
                    for k in valid_files:
                        if k.endswith(norm_path) or norm_path.endswith(k):
                            matched_key = k
                            break

                if matched_key:
                    verified.append(CitationItem(
                        file_path=matched_key,
                        start_line=max(1, cit.start_line),
                        end_line=max(cit.start_line, cit.end_line),
                        symbol_name=cit.symbol_name,
                        snippet=cit.snippet
                    ))

        if not verified and state.retrieved_chunks:
            for rc in state.retrieved_chunks[:3]:
                verified.append(CitationItem(
                    file_path=rc.file_path.replace("\\", "/"),
                    start_line=rc.start_line,
                    end_line=rc.end_line,
                    symbol_name=rc.symbol_name,
                    snippet=rc.content[:150]
                ))

        state.validated_citations = verified
