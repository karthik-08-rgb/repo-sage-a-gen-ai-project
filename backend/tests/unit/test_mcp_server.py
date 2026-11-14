import pytest
try:
    from mcp_server import (
        mcp,
        list_repositories,
        search_codebase,
        review_code,
        list_repositories_resource,
        list_repository_files_resource,
    )
    import mcp_server as mcp_mod
except ImportError:
    from backend.mcp_server import (
        mcp,
        list_repositories,
        search_codebase,
        review_code,
        list_repositories_resource,
        list_repository_files_resource,
    )
    import backend.mcp_server as mcp_mod


@pytest.mark.asyncio
async def test_mcp_registration():
    """Verify that all RepoSage MCP tools, resources, and prompts are properly registered."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "list_repositories" in tool_names
    assert "search_codebase" in tool_names
    assert "review_code" in tool_names
    assert "diagnose_error" in tool_names
    assert "ask_codebase" in tool_names

    resources = await mcp.list_resources()
    resource_uris = [r.uri for r in resources]
    assert "reposage://repositories" in resource_uris

    prompts = await mcp.list_prompts()
    prompt_names = [p.name for p in prompts]
    assert "debug_workflow" in prompt_names
    assert "code_review_workflow" in prompt_names


def test_mcp_list_repositories_safe():
    """Verify list_repositories returns formatted string without raising an exception."""
    res = list_repositories()
    assert isinstance(res, str)
    assert len(res) > 0


def test_mcp_search_codebase_invalid_repo_safe():
    """Verify search_codebase returns a clean error string on invalid repository without crashing."""
    res = search_codebase(repository_id="non-existent-uuid-000", query="test")
    assert "does not exist in RepoSage database" in res


def test_mcp_review_code_missing_args_safe():
    """Verify review_code rejects execution when neither file_path nor code_snippet is supplied."""
    res = review_code(repository_id="fake-id", file_path=None, code_snippet=None)
    assert "Error: You must provide either" in res


def test_mcp_resources_render_repository_and_files(db_session, test_user, monkeypatch):
    """Verify MCP resource handlers render repositories and files without attribute errors."""
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile
    from app.models.code_chunk import CodeChunk

    repo = Repository(
        user_id=test_user.id,
        name="MCPTestRepo",
        source_type="github_public",
        source_url="https://github.com/example/mcptest.git",
        primary_language="python",
        status="ready",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    rf = RepositoryFile(
        repository_id=repo.id,
        file_path="app/main.py",
        language="python",
        file_size=128,
    )
    db_session.add(rf)
    db_session.commit()
    db_session.refresh(rf)

    chunk = CodeChunk(
        repository_id=repo.id,
        file_id=rf.id,
        content="def main():\n    pass",
        symbol_name="main",
        symbol_type="function",
        start_line=1,
        end_line=2,
        language="python",
    )
    db_session.add(chunk)
    db_session.commit()

    class _NoCloseSessionProxy:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            pass

    monkeypatch.setattr(mcp_mod, "SessionLocal", lambda: _NoCloseSessionProxy(db_session))

    repos_md = list_repositories_resource()
    assert "MCPTestRepo" in repos_md
    assert "python" in repos_md
    assert "https://github.com/example/mcptest.git" in repos_md

    files_md = list_repository_files_resource(repo.id)
    assert "app/main.py" in files_md
    assert "128 bytes" in files_md
    assert "1 AST chunks" in files_md
