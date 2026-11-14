import pytest
from qdrant_client import QdrantClient
from app.services.retrieval.qdrant_service import QdrantService


@pytest.fixture
def memory_qdrant():
    svc = QdrantService.__new__(QdrantService)
    svc.collection_name = "test_collection"
    svc.vector_size = 8
    svc.client = QdrantClient(":memory:")
    svc._ensure_collection()
    return svc


def test_qdrant_upsert_and_filtered_search(memory_qdrant):
    repo_id = "test-repo-123"
    other_repo = "other-repo-456"

    chunks_data = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "file_path": "app/auth.py",
            "symbol_name": "authenticate_user",
            "symbol_type": "function",
            "start_line": 10,
            "end_line": 25,
            "language": "python",
            "content": "def authenticate_user(): pass",
            "chunk_type": "symbol"
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "embedding": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "file_path": "app/db.py",
            "symbol_name": "get_db",
            "symbol_type": "function",
            "start_line": 5,
            "end_line": 15,
            "language": "python",
            "content": "def get_db(): pass",
            "chunk_type": "symbol"
        }
    ]

    count = memory_qdrant.upsert_chunks(repo_id, chunks_data)
    assert count == 2

    # Vector search matching first chunk
    query_vec = [0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    hits = memory_qdrant.search_vectors(query_vec, repository_id=repo_id, top_k=5)
    assert len(hits) == 2
    assert hits[0]["file_path"] == "app/auth.py"
    assert hits[0]["symbol_name"] == "authenticate_user"

    # Repository isolation test: other_repo should return 0 hits
    other_hits = memory_qdrant.search_vectors(query_vec, repository_id=other_repo, top_k=5)
    assert len(other_hits) == 0

    # File filter test
    file_hits = memory_qdrant.search_vectors(query_vec, repository_id=repo_id, top_k=5, file_filter="db.py")
    assert len(file_hits) == 1
    assert file_hits[0]["file_path"] == "app/db.py"


def test_qdrant_delete_vectors(memory_qdrant):
    repo_id = "test-repo-delete"
    chunks_data = [
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "embedding": [1.0] * 8,
            "file_path": "app/main.py",
            "symbol_name": "main",
            "symbol_type": "function",
            "start_line": 1,
            "end_line": 5,
            "language": "python",
            "content": "def main(): pass"
        }
    ]
    memory_qdrant.upsert_chunks(repo_id, chunks_data)
    hits = memory_qdrant.search_vectors([1.0] * 8, repository_id=repo_id, top_k=5)
    assert len(hits) == 1

    memory_qdrant.delete_repository_vectors(repo_id)
    hits_after = memory_qdrant.search_vectors([1.0] * 8, repository_id=repo_id, top_k=5)
    assert len(hits_after) == 0
