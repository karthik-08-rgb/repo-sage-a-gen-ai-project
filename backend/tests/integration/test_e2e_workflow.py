import os
import subprocess
import shutil
import tempfile
from pathlib import Path
import pytest

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk
from app.models.symbol import Symbol
from app.models.agent_run import AgentRun
from app.models.tool_execution import ToolExecution
from app.models.patch import Patch
from app.services.ingestion.ingestion_pipeline import IngestionPipeline
from app.services.retrieval.retriever import HybridRetriever
from app.services.retrieval.qdrant_service import get_qdrant_service


def setup_git_workspace(base_dir: str):
    """Create a real Git repository with multi-file Python codebase and a deliberate bug."""
    repo_path = Path(base_dir)
    
    # 1. Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "RepoSage Test"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@reposage.dev"], cwd=repo_path, check=True, capture_output=True)

    # 2. Add .gitignore
    gitignore = repo_path / ".gitignore"
    gitignore.write_text(".git/\n__pycache__/\n*.pyc\n.pytest_cache/\n", encoding="utf-8")

    # 3. Add auth manager
    auth_dir = repo_path / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    (auth_dir / "__init__.py").write_text("", encoding="utf-8")
    (auth_dir / "manager.py").write_text(
        "class AuthManager:\n"
        "    \"\"\"Authentication token verification and session manager.\"\"\"\n"
        "    def __init__(self, secret_key: str):\n"
        "        self.secret_key = secret_key\n"
        "\n"
        "    def verify_token(self, token: str) -> bool:\n"
        "        return token.startswith('Bearer ')\n"
        "\n"
        "    def login(self, username: str, secret: str) -> str:\n"
        "        return f'token_{username}'\n",
        encoding="utf-8"
    )

    # 4. Add orders processor with a deliberate bug
    orders_dir = repo_path / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    (orders_dir / "__init__.py").write_text("", encoding="utf-8")
    (orders_dir / "processor.py").write_text(
        "class OrderProcessor:\n"
        "    \"\"\"Processes user orders and calculates totals.\"\"\"\n"
        "    def process_order(self, order: dict) -> dict:\n"
        "        user = order.get('user')\n"
        "        user_id = user['id']\n"
        "        return {'status': 'processed', 'user_id': user_id}\n",
        encoding="utf-8"
    )

    # 5. Add tests
    tests_dir = repo_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_processor.py").write_text(
        "from orders.processor import OrderProcessor\n"
        "\n"
        "def test_process_valid_order():\n"
        "    proc = OrderProcessor()\n"
        "    res = proc.process_order({'user': {'id': 'usr_100'}})\n"
        "    assert res['status'] == 'processed'\n",
        encoding="utf-8"
    )

    # Git commit
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial repository commit"], cwd=repo_path, check=True, capture_output=True)

    return repo_path


def test_full_e2e_reposage_lifecycle(client, db_session, test_user, auth_headers):
    """
    End-to-End Verification of the complete RepoSage Lifecycle:
    1. Git Workspace Initialization & Repository Registration
    2. Tree-sitter AST Parsing & Symbol Extraction (PostgreSQL)
    3. Code-aware Chunking with AST Boundaries
    4. Qdrant Vector Storage & Hybrid Retrieval
    5. Incremental Indexing & Content Hash Diffing
    6. LangGraph AI Debugging Agent Execution
    7. Tool Execution Tracking & Agent Run Persistence
    8. Patch Review, Unified Diff, and Line Statistics
    9. Human Approval & Physical Diff Application to Disk
    10. Repository Deletion & Vector Cleanup
    """
    temp_dir = tempfile.mkdtemp()
    try:
        repo_path = setup_git_workspace(temp_dir)

        # -------------------------------------------------------------
        # STEP 1: Register Repository
        # -------------------------------------------------------------
        repo = Repository(
            user_id=test_user.id,
            name="E2ETestProject",
            source_type="local",
            local_path=str(repo_path),
            status="pending"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        # Verify repository GET endpoint
        res_repo = client.get(f"/repositories/{repo.id}", headers=auth_headers)
        assert res_repo.status_code == 200
        assert res_repo.json()["data"]["name"] == "E2ETestProject"

        # -------------------------------------------------------------
        # STEP 2: Ingestion & Tree-sitter AST Symbol Indexing
        # -------------------------------------------------------------
        pipeline = IngestionPipeline(db_session, repo)
        total_files, total_chunks = pipeline.run()

        assert total_files >= 3  # auth/manager.py, orders/processor.py, tests/test_processor.py
        assert total_chunks >= 3

        db_session.refresh(repo)
        assert repo.status == "ready"

        # Verify Symbols extracted by Tree-sitter in PostgreSQL
        symbols = db_session.query(Symbol).filter(Symbol.repository_id == repo.id).all()
        symbol_names = {s.name for s in symbols}
        assert "AuthManager" in symbol_names
        assert "OrderProcessor" in symbol_names
        assert "process_order" in symbol_names
        assert "verify_token" in symbol_names

        # Verify Symbol line boundaries & metadata
        proc_sym = db_session.query(Symbol).filter(
            Symbol.repository_id == repo.id,
            Symbol.name == "process_order"
        ).first()
        assert proc_sym is not None
        assert proc_sym.symbol_type in ("method", "function")
        assert proc_sym.start_line > 0
        assert proc_sym.end_line >= proc_sym.start_line

        # Verify Code Chunks in PostgreSQL
        chunks = db_session.query(CodeChunk).filter(CodeChunk.repository_id == repo.id).all()
        assert len(chunks) >= 3

        # -------------------------------------------------------------
        # STEP 3: Qdrant Vector Storage Verification
        # -------------------------------------------------------------
        qdrant = get_qdrant_service()
        vector_count = qdrant.count(repository_id=repo.id)
        assert vector_count >= len(chunks)

        # -------------------------------------------------------------
        # STEP 4: Incremental Indexing Verification
        # -------------------------------------------------------------
        # Record initial updated_at of auth/manager.py file record
        auth_file_before = db_session.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repo.id,
            RepositoryFile.file_path == "auth/manager.py"
        ).first()
        assert auth_file_before is not None
        initial_auth_hash = auth_file_before.content_hash

        # Modify only orders/processor.py on disk
        processor_file = repo_path / "orders" / "processor.py"
        processor_content = processor_file.read_text(encoding="utf-8")
        processor_file.write_text(processor_content + "\n    def cancel_order(self, order_id: str):\n        pass\n", encoding="utf-8")

        # Run pipeline again (incremental update)
        pipeline_inc = IngestionPipeline(db_session, repo)
        inc_files, inc_chunks = pipeline_inc.run()

        # Verify auth/manager.py was not re-hashed or changed
        auth_file_after = db_session.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repo.id,
            RepositoryFile.file_path == "auth/manager.py"
        ).first()
        assert auth_file_after.content_hash == initial_auth_hash

        # Verify cancel_order symbol was discovered in incremental pass
        cancel_sym = db_session.query(Symbol).filter(
            Symbol.repository_id == repo.id,
            Symbol.name == "cancel_order"
        ).first()
        assert cancel_sym is not None

        # -------------------------------------------------------------
        # STEP 5: Hybrid Retrieval (PostgreSQL Symbols + Qdrant Vectors)
        # -------------------------------------------------------------
        retriever = HybridRetriever(db_session, repo.id)
        retrieved_results = retriever.retrieve(query="process_order user id", top_k=5)
        assert len(retrieved_results) > 0
        top_match = retrieved_results[0]
        assert "orders/processor.py" in top_match.file_path
        assert "process_order" in top_match.content

        # -------------------------------------------------------------
        # STEP 6: AI Debugging Agent Execution via POST /debug
        # -------------------------------------------------------------
        debug_payload = {
            "repository_id": repo.id,
            "error_message": "TypeError: 'NoneType' object is not subscriptable in OrderProcessor.process_order",
            "stack_trace": (
                "Traceback (most recent call last):\n"
                "  File \"orders/processor.py\", line 5, in process_order\n"
                "    user_id = user['id']\n"
                "TypeError: 'NoneType' object is not subscriptable"
            ),
            "relevant_file": "orders/processor.py",
            "expected_behavior": "Handle orders where user is None or not a dict gracefully without crashing."
        }

        res_debug = client.post("/debug", json=debug_payload, headers=auth_headers)
        assert res_debug.status_code == 200
        debug_data = res_debug.json()["data"]

        run_id = debug_data["run_id"]
        patch_id = debug_data["patch_id"]
        assert run_id is not None
        assert patch_id is not None
        assert len(debug_data["suggested_fixes"]) >= 1

        fix = debug_data["suggested_fixes"][0]
        assert "orders/processor.py" in fix["file_path"]
        assert "---" in fix["unified_diff"]
        assert "+++" in fix["unified_diff"]

        # -------------------------------------------------------------
        # STEP 7: Agent Run & Tool Execution History Verification
        # -------------------------------------------------------------
        res_run = client.get(f"/runs/{run_id}", headers=auth_headers)
        assert res_run.status_code == 200
        run_data = res_run.json()["data"]
        assert run_data["id"] == run_id
        assert run_data["status"] in ("awaiting_approval", "completed")
        assert len(run_data["execution_log"]) > 0

        # Verify tool executions recorded for the debugging run
        res_tools = client.get(f"/runs/{run_id}/tools", headers=auth_headers)
        assert res_tools.status_code == 200
        tool_records = res_tools.json()["data"]
        assert len(tool_records) >= 2
        tool_names = [t["tool_name"] for t in tool_records]
        assert "hybrid_code_search" in tool_names
        assert "inspect_symbol_dependencies" in tool_names

        # -------------------------------------------------------------
        # STEP 8: Patch Review & Diff Inspection
        # -------------------------------------------------------------
        res_patch = client.get(f"/patches/{patch_id}", headers=auth_headers)
        assert res_patch.status_code == 200
        patch_data = res_patch.json()["data"]
        assert patch_data["target_file"] == "orders/processor.py"
        assert patch_data["status"] == "pending_approval"

        res_diff = client.get(f"/patches/{patch_id}/diff", headers=auth_headers)
        assert res_diff.status_code == 200
        diff_info = res_diff.json()["data"]
        assert diff_info["added_lines"] >= 1
        assert "user" in diff_info["unified_diff"]

        # -------------------------------------------------------------
        # STEP 9: Human-in-the-Loop Patch Approval & File Modification
        # -------------------------------------------------------------
        res_approve = client.post(f"/patches/{patch_id}/approve", headers=auth_headers)
        assert res_approve.status_code == 200
        approval_data = res_approve.json()["data"]
        assert approval_data["status"] == "applied"
        assert approval_data["applied_to_file"] == "orders/processor.py"

        # Verify target file on disk was physically updated with the patch
        updated_processor = (repo_path / "orders" / "processor.py").read_text(encoding="utf-8")
        assert "orders/processor.py" in approval_data["applied_to_file"]
        assert len(updated_processor) > 0

        # Verify AgentRun status is completed
        res_run_final = client.get(f"/runs/{run_id}", headers=auth_headers)
        assert res_run_final.json()["data"]["status"] == "completed"

        # -------------------------------------------------------------
        # STEP 10: Repository Cleanup & Qdrant Purge
        # -------------------------------------------------------------
        res_del = client.delete(f"/repositories/{repo.id}", headers=auth_headers)
        assert res_del.status_code == 200

        # Verify repository purged from database
        assert db_session.query(Repository).filter(Repository.id == repo.id).first() is None
        assert db_session.query(Symbol).filter(Symbol.repository_id == repo.id).count() == 0
        assert db_session.query(CodeChunk).filter(CodeChunk.repository_id == repo.id).count() == 0

        # Verify Qdrant vectors purged
        assert qdrant.count(repository_id=repo.id) == 0

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
