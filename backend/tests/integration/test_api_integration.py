import json
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk


def test_health_and_readiness(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

    r2 = client.get("/ready")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ready"


def test_auth_workflow(client):
    # Register
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "user1@reposage.dev",
        "password": "Password123!"
    })
    assert reg_res.status_code == 201
    assert reg_res.json()["data"]["email"] == "user1@reposage.dev"

    # Login
    login_res = client.post("/api/v1/auth/login", json={
        "email": "user1@reposage.dev",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    tokens = login_res.json()["data"]
    access_token = tokens["access_token"]
    assert access_token is not None

    # Get profile
    profile_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert profile_res.status_code == 200
    assert profile_res.json()["data"]["email"] == "user1@reposage.dev"


def test_repository_chat_and_debug(client, db_session, test_user, auth_headers):
    # Seed a repository
    repo = Repository(
        user_id=test_user.id,
        name="DemoProject",
        source_type="github_public",
        status="ready",
        total_files=1,
        total_chunks=1
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # Seed file & chunk
    rf = RepositoryFile(
        repository_id=repo.id,
        file_path="app/auth.py",
        language="python",
        file_size=200
    )
    db_session.add(rf)
    db_session.commit()
    db_session.refresh(rf)

    chunk = CodeChunk(
        repository_id=repo.id,
        file_id=rf.id,
        content="def authenticate(user, password):\n    return check_hash(password)",
        symbol_name="authenticate",
        symbol_type="function",
        start_line=1,
        end_line=2,
        language="python"
    )
    chunk.embedding = [0.1] * 1536
    chunk.chunk_metadata = {"file_path": "app/auth.py"}
    db_session.add(chunk)
    db_session.commit()

    # Test list repositories
    list_res = client.get("/api/v1/repositories", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) == 1

    # Test Search
    search_res = client.post("/api/v1/search", json={
        "repository_id": repo.id,
        "query": "authenticate user password",
        "search_type": "hybrid",
        "top_k": 5
    }, headers=auth_headers)
    assert search_res.status_code == 200
    assert search_res.json()["data"]["total_results"] >= 1

    # Test Chat
    chat_res = client.post("/api/v1/chat", json={
        "repository_id": repo.id,
        "question": "How does the authentication function work?"
    }, headers=auth_headers)
    assert chat_res.status_code == 200
    data = chat_res.json()["data"]
    assert data["role"] == "assistant"
    assert len(data["content"]) > 10

    # Test Debug Analyze
    debug_res = client.post("/api/v1/debug/analyze", json={
        "repository_id": repo.id,
        "error_message": "AttributeError: 'NoneType' object has no attribute 'check_hash'",
        "relevant_file": "app/auth.py"
    }, headers=auth_headers)
    assert debug_res.status_code == 200
    assert debug_res.json()["data"]["potential_root_cause"] is not None

    # Test Code Review
    review_res = client.post("/api/v1/review", json={
        "repository_id": repo.id,
        "code_snippet": "eval('import os; os.system(\"rm -rf /\")')"
    }, headers=auth_headers)
    assert review_res.status_code == 200
    findings = review_res.json()["data"]["findings"]
    assert any(f["severity"] == "Critical" for f in findings)

    # Test Agent Workflow Endpoint
    agent_res = client.post("/api/v1/chat/agent", json={
        "repository_id": repo.id,
        "query": "Where is the authenticate function located?"
    }, headers=auth_headers)
    assert agent_res.status_code == 200
    agent_data = agent_res.json()["data"]
    assert agent_data["intent"] in ["lookup", "general_codebase"]
    assert len(agent_data["execution_log"]) > 0

    # Test One-Click Diff Application
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_repo_dir:
        repo.local_path = tmp_repo_dir
        db_session.commit()
        sample_file = f"{tmp_repo_dir}/app/auth.py"
        import os
        os.makedirs(os.path.dirname(sample_file), exist_ok=True)
        with open(sample_file, "w") as f:
            f.write("def authenticate(user, password):\n    return check_hash(password)\n")

        apply_res = client.post("/api/v1/code/apply-approved-diff", json={
            "repository_id": repo.id,
            "file_path": "app/auth.py",
            "unified_diff": "--- a/app/auth.py\n+++ b/app/auth.py\n@@ -1,2 +1,3 @@\n def authenticate(user, password):\n+    assert user is not None\n     return check_hash(password)\n"
        }, headers=auth_headers)
        assert apply_res.status_code == 200
        assert apply_res.json()["data"]["status"] == "applied"

        with open(sample_file, "r") as f:
            updated_content = f.read()
        assert "assert user is not None" in updated_content
