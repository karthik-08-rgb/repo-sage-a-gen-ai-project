import math
import re
import logging
from typing import List, Dict, Optional, Any, Tuple, cast
from sqlalchemy.orm import Session
from app.models.code_chunk import CodeChunk
from app.models.repository_file import RepositoryFile
from app.models.symbol import Symbol
from app.core.config import settings
from app.services.embeddings.provider import get_embedding_provider
from app.services.retrieval.qdrant_service import get_qdrant_service

logger = logging.getLogger(__name__)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0
    return dot / (norm1 * norm2)


class RetrievedChunk:
    def __init__(
        self,
        chunk: CodeChunk,
        score: float,
        retrieval_method: str,
        file_path: str
    ):
        self.chunk = chunk
        self.score = score
        self.retrieval_method = retrieval_method
        self.file_path = file_path

    @property
    def id(self) -> str:
        return cast(str, self.chunk.id)

    @property
    def content(self) -> str:
        return cast(str, self.chunk.content)

    @property
    def symbol_name(self) -> Optional[str]:
        return cast(Optional[str], self.chunk.symbol_name)

    @property
    def symbol_type(self) -> Optional[str]:
        return cast(Optional[str], self.chunk.symbol_type)

    @property
    def start_line(self) -> int:
        return cast(int, self.chunk.start_line)

    @property
    def end_line(self) -> int:
        return cast(int, self.chunk.end_line)

    @property
    def language(self) -> Optional[str]:
        return cast(Optional[str], self.chunk.language)


class HybridRetriever:
    """
    Hybrid Retrieval Engine combining:
    1. Qdrant vector similarity search
    2. Exact & partial symbol lookup from PostgreSQL symbols table
    3. Keyword / lexical full-text search
    4. Reciprocal Rank Fusion (RRF) with symbol boosting
    """
    def __init__(self, db: Session, repository_id: str):
        self.db = db
        self.repository_id = repository_id
        self.embedder = get_embedding_provider()
        self.qdrant = get_qdrant_service()

    def search(
        self,
        query: str,
        search_type: str = "hybrid",
        top_k: int = settings.TOP_K_RETRIEVAL,
        file_filter: Optional[str] = None
    ) -> List[RetrievedChunk]:
        """
        Execute dense, keyword, symbol, or hybrid retrieval.
        """
        if search_type == "dense":
            return self._dense_search(query, top_k, file_filter)
        elif search_type == "keyword":
            return self._keyword_search(query, top_k, file_filter)
        elif search_type == "symbol":
            return self._symbol_search(query, top_k, file_filter)
        else:
            return self._hybrid_search(query, top_k, file_filter)

    def retrieve(
        self,
        query: str,
        search_type: str = "hybrid",
        top_k: int = settings.TOP_K_RETRIEVAL,
        file_filter: Optional[str] = None
    ) -> List[RetrievedChunk]:
        """Convenience alias for search."""
        return self.search(query=query, search_type=search_type, top_k=top_k, file_filter=file_filter)

    def _dense_search(self, query: str, top_k: int, file_filter: Optional[str]) -> List[RetrievedChunk]:
        """Query Qdrant for semantic similarity."""
        query_vec = self.embedder.embed_text(query)
        qdrant_hits = self.qdrant.search_vectors(
            query_vector=query_vec,
            repository_id=self.repository_id,
            top_k=top_k,
            file_filter=file_filter
        )

        results: List[RetrievedChunk] = []
        if qdrant_hits:
            chunk_ids = [h["chunk_id"] for h in qdrant_hits]
            chunk_models = {
                c.id: c for c in self.db.query(CodeChunk).filter(CodeChunk.id.in_(chunk_ids)).all()
            }
            for hit in qdrant_hits:
                cid = hit["chunk_id"]
                ch = chunk_models.get(cid)
                if ch:
                    results.append(RetrievedChunk(
                        chunk=ch,
                        score=round(hit["score"], 4),
                        retrieval_method="dense_qdrant",
                        file_path=hit["file_path"]
                    ))

        # Fallback if Qdrant returned no results (e.g. before initial indexing)
        if not results:
            candidate_chunks = self._load_candidate_chunks(file_filter)
            scored: List[Tuple[CodeChunk, float, str]] = []
            for ch in candidate_chunks:
                emb = ch.embedding
                if emb:
                    sim = cosine_similarity(query_vec, emb)
                    fp = ch.chunk_metadata.get("file_path", "")
                    scored.append((ch, sim, fp))
            scored.sort(key=lambda x: x[1], reverse=True)
            results = [
                RetrievedChunk(chunk=ch, score=round(sc, 4), retrieval_method="dense", file_path=fp)
                for ch, sc, fp in scored[:top_k]
            ]

        return results

    def _symbol_search(self, query: str, top_k: int, file_filter: Optional[str]) -> List[RetrievedChunk]:
        """Search PostgreSQL symbols table for matching functions, classes, methods."""
        tokens = re.findall(r"[a-zA-Z0-9_]+", query)
        if not tokens:
            return []

        # Find matching symbols in database
        sym_query = self.db.query(Symbol).filter(Symbol.repository_id == self.repository_id)
        if file_filter:
            sym_query = sym_query.join(RepositoryFile).filter(RepositoryFile.file_path.ilike(f"%{file_filter}%"))

        # Look for symbol names matching any token
        all_symbols = sym_query.all()
        scored_symbols: List[Tuple[Symbol, float]] = []

        for sym in all_symbols:
            sym_name_lower = sym.name.lower()
            score = 0.0
            for t in tokens:
                t_lower = t.lower()
                if sym_name_lower == t_lower:
                    score = max(score, 1.0)
                elif t_lower in sym_name_lower:
                    score = max(score, len(t_lower) / len(sym_name_lower))

            if score > 0:
                scored_symbols.append((sym, score))

        scored_symbols.sort(key=lambda x: x[1], reverse=True)

        # Retrieve corresponding CodeChunks that overlap with matching symbols
        results: List[RetrievedChunk] = []
        seen_chunks = set()

        for sym, sc in scored_symbols[:top_k]:
            matching_chunks = self.db.query(CodeChunk).filter(
                CodeChunk.repository_id == self.repository_id,
                CodeChunk.file_id == sym.file_id,
                CodeChunk.start_line <= sym.end_line,
                CodeChunk.end_line >= sym.start_line
            ).all()

            for ch in matching_chunks:
                if ch.id not in seen_chunks:
                    seen_chunks.add(ch.id)
                    fp = ch.chunk_metadata.get("file_path", "")
                    results.append(RetrievedChunk(
                        chunk=ch,
                        score=round(sc, 4),
                        retrieval_method="symbol_index",
                        file_path=fp
                    ))

        return results[:top_k]

    def _keyword_search(self, query: str, top_k: int, file_filter: Optional[str]) -> List[RetrievedChunk]:
        """Lexical search across chunk content, file paths, and symbol names."""
        tokens = set(re.findall(r"[a-zA-Z0-9_]{3,}", query.lower()))
        if not tokens:
            return []

        chunks = self._load_candidate_chunks(file_filter)
        scored: List[Tuple[CodeChunk, float, str]] = []

        for ch in chunks:
            content_lower = ch.content.lower()
            sym_lower = (ch.symbol_name or "").lower()
            file_p = ch.chunk_metadata.get("file_path", "").lower()

            matches = 0.0
            for t in tokens:
                if t in sym_lower:
                    matches += 5.0
                if t in file_p:
                    matches += 3.0
                if t in content_lower:
                    matches += 1.0

            if matches > 0:
                score = matches / (len(tokens) + 2.0)
                scored.append((ch, score, ch.chunk_metadata.get("file_path", "")))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            RetrievedChunk(chunk=ch, score=round(sc, 4), retrieval_method="keyword", file_path=fp)
            for ch, sc, fp in scored[:top_k]
        ]

    def _hybrid_search(self, query: str, top_k: int, file_filter: Optional[str]) -> List[RetrievedChunk]:
        """
        Reciprocal Rank Fusion (RRF) combining:
        - Qdrant dense vector similarity
        - PostgreSQL symbols index
        - Keyword FTS
        """
        dense_results = self._dense_search(query, top_k=top_k * 2, file_filter=file_filter)
        keyword_results = self._keyword_search(query, top_k=top_k * 2, file_filter=file_filter)
        symbol_results = self._symbol_search(query, top_k=top_k, file_filter=file_filter)

        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Tuple[CodeChunk, str]] = {}
        rrf_k = 60.0

        for rank, res in enumerate(dense_results, start=1):
            cid = res.id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))
            chunk_map[cid] = (res.chunk, res.file_path)

        for rank, res in enumerate(keyword_results, start=1):
            cid = res.id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))
            chunk_map[cid] = (res.chunk, res.file_path)

        for rank, res in enumerate(symbol_results, start=1):
            cid = res.id
            # Exact symbol matches get high boost
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.8 / (rrf_k + rank))
            chunk_map[cid] = (res.chunk, res.file_path)

        sorted_cids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        merged: List[RetrievedChunk] = []
        for cid, score in sorted_cids[:top_k]:
            if cid in chunk_map:
                ch, fp = chunk_map[cid]
                merged.append(RetrievedChunk(
                    chunk=ch,
                    score=round(score * 100, 4),
                    retrieval_method="hybrid_rrf",
                    file_path=fp
                ))

        return merged

    def _load_candidate_chunks(self, file_filter: Optional[str]) -> List[CodeChunk]:
        q = self.db.query(CodeChunk).filter(CodeChunk.repository_id == self.repository_id)
        if file_filter:
            q = q.join(RepositoryFile).filter(RepositoryFile.file_path.ilike(f"%{file_filter}%"))
        return q.all()
