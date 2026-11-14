import pytest
import tempfile
import shutil
from pathlib import Path
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.agent_run import AgentRun
from app.models.tool_execution import ToolExecution
from app.models.patch import Patch
from app.models.user import User


def test_get_agent_run_and_tool_executions(client, db_session, test_user, auth_headers):
    # Create repo
    repo = Repository(
        user_id=test_user.id,
        name="AgentRunTestRepo",
        source_type="local",
        status="ready"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # Create run
    run = AgentRun(
        repository_id=repo.id,
        user_id=test_user.id,
        status="awaiting_approval",
        current_step="validate_patch",
        iterations=3,
        query="AttributeError: NoneType has no attribute 'val'",
        root_cause_analysis="Null pointer dereference in process_data.",
        proposed_fix_summary="Add None-check guard before accessing val attribute.",
        generated_tests="def test_process_none():\n    assert process(None) is None"
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    # Create tools
    t1 = ToolExecution(
        agent_run_id=run.id,
        tool_name="qdrant_retriever",
        arguments={"query": "AttributeError val", "top_k": 3},
        result={"chunks_found": 3},
        status="success",
        execution_time_ms=120
    )
    t2 = ToolExecution(
        agent_run_id=run.id,
        tool_name="ast_parser",
        arguments={"file_path": "process.py"},
        result={"symbols": ["process_data"]},
        status="success",
        execution_time_ms=45
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Test GET /runs/{run_id} via root endpoint
    res_root = client.get(f"/runs/{run.id}", headers=auth_headers)
    assert res_root.status_code == 200
    data = res_root.json()["data"]
    assert data["id"] == run.id
    assert data["status"] == "awaiting_approval"
    assert "Null pointer" in data["root_cause_analysis"]
    assert data["iterations"] == 3

    # Test GET /api/v1/runs/{run_id}
    res_v1 = client.get(f"/api/v1/runs/{run.id}", headers=auth_headers)
    assert res_v1.status_code == 200
    assert res_v1.json()["data"]["id"] == run.id

    # Test GET /runs/{run_id}/tools via root endpoint
    res_tools = client.get(f"/runs/{run.id}/tools", headers=auth_headers)
    assert res_tools.status_code == 200
    tools = res_tools.json()["data"]
    assert len(tools) == 2
    assert tools[0]["tool_name"] == "qdrant_retriever"
    assert tools[1]["tool_name"] == "ast_parser"

    # Test 404 for nonexistent run
    res_404 = client.get("/runs/nonexistent-run-id", headers=auth_headers)
    assert res_404.status_code == 404


def test_patch_approval_applies_diff_to_disk(client, db_session, test_user, auth_headers):
    # Setup temporary directory simulating repo workspace
    temp_dir = tempfile.mkdtemp()
    try:
        source_file = Path(temp_dir) / "calculator.py"
        source_file.write_text(
            "def divide(a, b):\n"
            "    return a / b\n",
            encoding="utf-8"
        )

        repo = Repository(
            user_id=test_user.id,
            name="PatchDiskTestRepo",
            source_type="local",
            local_path=temp_dir,
            status="ready"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        repo_file = RepositoryFile(
            repository_id=repo.id,
            file_path="calculator.py",
            language="python",
            file_size=len(source_file.read_bytes())
        )
        db_session.add(repo_file)

        run = AgentRun(
            repository_id=repo.id,
            user_id=test_user.id,
            query="Prevent zero division error in divide()",
            status="awaiting_approval",
            current_step="awaiting_approval"
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        # Unified diff adding ZeroDivisionError check
        unified_diff = (
            "--- a/calculator.py\n"
            "+++ b/calculator.py\n"
            "@@ -1,2 +1,4 @@\n"
            " def divide(a, b):\n"
            "+    if b == 0:\n"
            "+        raise ValueError('Division by zero is undefined')\n"
            "     return a / b\n"
        )

        patch = Patch(
            repository_id=repo.id,
            agent_run_id=run.id,
            user_id=test_user.id,
            target_file="calculator.py",
            unified_diff=unified_diff,
            description="Added zero check before division to prevent crash",
            status="pending"
        )
        db_session.add(patch)
        db_session.commit()
        db_session.refresh(patch)

        # 1. GET /patches/{id}
        res_get = client.get(f"/patches/{patch.id}", headers=auth_headers)
        assert res_get.status_code == 200
        assert res_get.json()["data"]["target_file"] == "calculator.py"

        # 2. GET /patches/{id}/diff
        res_diff = client.get(f"/patches/{patch.id}/diff", headers=auth_headers)
        assert res_diff.status_code == 200
        diff_data = res_diff.json()["data"]
        assert diff_data["added_lines"] == 2
        assert diff_data["removed_lines"] == 0

        # 3. POST /patches/{id}/approve
        res_approve = client.post(f"/patches/{patch.id}/approve", headers=auth_headers)
        assert res_approve.status_code == 200
        assert res_approve.json()["data"]["status"] == "applied"

        # Verify disk modification
        updated_content = source_file.read_text(encoding="utf-8")
        assert "if b == 0:" in updated_content
        assert "raise ValueError('Division by zero is undefined')" in updated_content

        # Verify DB records updated
        db_session.refresh(patch)
        assert patch.status == "applied"
        assert patch.approved_at is not None

        db_session.refresh(run)
        assert run.status == "completed"

        # 4. Approving already applied patch is idempotent
        res_reapprove = client.post(f"/patches/{patch.id}/approve", headers=auth_headers)
        assert res_reapprove.status_code == 200
        assert res_reapprove.json()["data"]["status"] == "applied"

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_patch_rejection_workflow(client, db_session, test_user, auth_headers):
    repo = Repository(
        user_id=test_user.id,
        name="RejectTestRepo",
        source_type="local",
        status="ready"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    run = AgentRun(
        repository_id=repo.id,
        user_id=test_user.id,
        query="Refactor main.py entrypoint",
        status="awaiting_approval"
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    patch = Patch(
        repository_id=repo.id,
        agent_run_id=run.id,
        user_id=test_user.id,
        target_file="app/main.py",
        unified_diff="--- a/main.py\n+++ b/main.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        status="pending"
    )
    db_session.add(patch)
    db_session.commit()
    db_session.refresh(patch)

    # Reject patch
    res_reject = client.post(f"/patches/{patch.id}/reject", headers=auth_headers)
    assert res_reject.status_code == 200
    assert res_reject.json()["data"]["status"] == "rejected"

    db_session.refresh(patch)
    assert patch.status == "rejected"
    assert patch.rejected_at is not None

    db_session.refresh(run)
    assert run.status == "rejected"


def test_patch_security_path_traversal_blocked(client, db_session, test_user, auth_headers):
    temp_dir = tempfile.mkdtemp()
    try:
        repo = Repository(
            user_id=test_user.id,
            name="TraversalSecurityRepo",
            source_type="local",
            local_path=temp_dir,
            status="ready"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        # Patch attempting directory traversal outside workspace
        patch = Patch(
            repository_id=repo.id,
            user_id=test_user.id,
            target_file="../../outside_secret.py",
            unified_diff="--- a\n+++ b\n@@ -1 +1 @@\n-safe\n+escaped\n",
            status="pending"
        )
        db_session.add(patch)
        db_session.commit()
        db_session.refresh(patch)

        res = client.post(f"/patches/{patch.id}/approve", headers=auth_headers)
        assert res.status_code == 400
        assert "Security violation" in res.json()["detail"]

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
