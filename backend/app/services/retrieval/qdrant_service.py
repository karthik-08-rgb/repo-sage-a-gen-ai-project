import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse
from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """
    Production Qdrant Vector Storage service.
    Handles collection management, point upserts, metadata payload indexing,
    repository and file-level filtered vector similarity retrieval.
    """

    _instance = None

    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.EMBEDDING_DIMENSION
        self.client: QdrantClient = self._init_client()
        self._ensure_collection()

    def _init_client(self) -> QdrantClient:
        """Connect to remote Qdrant service or fall back to local disk storage."""
        if settings.QDRANT_USE_MEMORY:
            logger.info("Initializing in-memory QdrantClient for test mode.")
            return QdrantClient(":memory:")

        # Attempt remote connection
        url = settings.QDRANT_URL or f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
        try:
            client = QdrantClient(url=url, api_key=settings.QDRANT_API_KEY, timeout=2.0, check_compatibility=False)
            # Ping
            client.get_collections()
            logger.info(f"Connected to Qdrant cluster at {url}")
            return client
        except Exception as e:
            logger.warning(
                f"Could not connect to external Qdrant at {url}: {e}. "
                "Operating with persistent embedded local Qdrant engine at ./data/qdrant_storage."
            )
            import os
            from pathlib import Path
            storage_dir = Path("./data/qdrant_storage").resolve()
            storage_dir.mkdir(parents=True, exist_ok=True)
            return QdrantClient(path=str(storage_dir))

    def _ensure_collection(self) -> None:
        """Verify collection exists; create with Cosine distance if absent."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection '{self.collection_name}' (dim={self.vector_size}, distance=Cosine)...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.vector_size,
                        distance=qmodels.Distance.COSINE
                    )
                )
                # Create payload indexes for efficient repository and file filtering
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="repository_id",
                        field_schema=qmodels.PayloadSchemaType.KEYWORD
                    )
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="file_path",
                        field_schema=qmodels.PayloadSchemaType.KEYWORD
                    )
                except Exception as idx_err:
                    logger.debug(f"Payload index creation note: {idx_err}")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection: {e}")

    def upsert_chunks(
        self,
        repository_id: str,
        chunks_data: List[Dict[str, Any]]
    ) -> int:
        """
        Batch upsert code chunk vectors and payloads to Qdrant.
        Each item in chunks_data must contain:
        id, embedding, content, file_path, start_line, end_line, symbol_name, symbol_type, language
        """
        if not chunks_data:
            return 0

        points: List[qmodels.PointStruct] = []
        for item in chunks_data:
            emb = item.get("embedding")
            if not emb:
                continue

            # Ensure embedding length matches
            if len(emb) != self.vector_size:
                if len(emb) < self.vector_size:
                    emb = list(emb) + [0.0] * (self.vector_size - len(emb))
                else:
                    emb = emb[:self.vector_size]

            point = qmodels.PointStruct(
                id=item["id"],
                vector=emb,
                payload={
                    "repository_id": repository_id,
                    "chunk_id": item["id"],
                    "file_path": item.get("file_path", ""),
                    "symbol_name": item.get("symbol_name") or "",
                    "symbol_type": item.get("symbol_type") or "",
                    "start_line": item.get("start_line", 1),
                    "end_line": item.get("end_line", 1),
                    "language": item.get("language") or "",
                    "chunk_type": item.get("chunk_type") or "symbol",
                    "content": item.get("content", ""),
                    "content_hash": item.get("content_hash", "")
                }
            )
            points.append(point)

        if not points:
            return 0

        # Upsert in batches of 100
        batch_size = 100
        total_upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=True
            )
            total_upserted += len(batch)

        logger.info(f"Upserted {total_upserted} vector points to Qdrant for repo {repository_id}")
        return total_upserted

    def search_vectors(
        self,
        query_vector: List[float],
        repository_id: str,
        top_k: int = 10,
        file_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search with repository and file-level filters.
        """
        if not query_vector:
            return []

        # Pad or slice vector to expected dimensions
        if len(query_vector) != self.vector_size:
            if len(query_vector) < self.vector_size:
                query_vector = list(query_vector) + [0.0] * (self.vector_size - len(query_vector))
            else:
                query_vector = query_vector[:self.vector_size]

        must_conditions: List[qmodels.Condition] = [
            qmodels.FieldCondition(
                key="repository_id",
                match=qmodels.MatchValue(value=repository_id)
            )
        ]

        if file_filter:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="file_path",
                    match=qmodels.MatchText(text=file_filter)
                )
            )

        query_filter = qmodels.Filter(must=must_conditions)

        try:
            # Query Qdrant
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True
            )

            hits = []
            for hit in results.points:
                payload = hit.payload or {}
                hits.append({
                    "chunk_id": payload.get("chunk_id", str(hit.id)),
                    "score": float(hit.score),
                    "file_path": payload.get("file_path", ""),
                    "symbol_name": payload.get("symbol_name"),
                    "symbol_type": payload.get("symbol_type"),
                    "start_line": payload.get("start_line", 1),
                    "end_line": payload.get("end_line", 1),
                    "language": payload.get("language"),
                    "content": payload.get("content", ""),
                    "chunk_type": payload.get("chunk_type", "symbol")
                })
            return hits
        except Exception as e:
            logger.error(f"Qdrant vector search failed: {e}")
            return []

    def count(self, repository_id: Optional[str] = None) -> int:
        """Count vector points in collection, optionally filtered by repository."""
        try:
            count_filter = None
            if repository_id:
                count_filter = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="repository_id",
                            match=qmodels.MatchValue(value=repository_id)
                        )
                    ]
                )
            res = self.client.count(
                collection_name=self.collection_name,
                count_filter=count_filter
            )
            return res.count
        except Exception as e:
            logger.warning(f"Failed to count Qdrant points: {e}")
            return 0

    def delete_repository_vectors(self, repository_id: str) -> None:
        """Purge all vector points associated with a repository."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="repository_id",
                                match=qmodels.MatchValue(value=repository_id)
                            )
                        ]
                    )
                ),
                wait=True
            )
            logger.info(f"Deleted Qdrant vectors for repository {repository_id}")
        except Exception as e:
            logger.warning(f"Could not delete Qdrant vectors for repo {repository_id}: {e}")

    def delete_file_vectors(self, repository_id: str, file_path: str) -> None:
        """Purge vector points for a specific file during incremental indexing."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="repository_id",
                                match=qmodels.MatchValue(value=repository_id)
                            ),
                            qmodels.FieldCondition(
                                key="file_path",
                                match=qmodels.MatchValue(value=file_path)
                            )
                        ]
                    )
                ),
                wait=True
            )
        except Exception as e:
            logger.warning(f"Failed deleting vectors for file {file_path}: {e}")


def get_qdrant_service() -> QdrantService:
    if QdrantService._instance is None:
        QdrantService._instance = QdrantService()
    return QdrantService._instance
