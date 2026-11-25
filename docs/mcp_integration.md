# Model Context Protocol (MCP) Integration

RepoSage provides a standards-compliant **Model Context Protocol (MCP)** server, enabling AI IDEs and assistants (such as Cursor, Claude Desktop, Antigravity, and VS Code) to directly interact with RepoSage's hybrid code search, 6-dimensional code reviewer, and stack trace debugger.

---

## 1. Architecture & Crash-Resilience Guarantee

The RepoSage MCP server is engineered with strict isolation so that your existing application will **never crash** or experience degraded performance:

1. **Process Decoupling**: The MCP server (`backend/mcp_server.py`) runs as an independent process. If an MCP client disconnects or an external LLM fails, the core FastAPI server (`localhost:8000`), Celery queue, and React frontend (`localhost:5173`) remain 100% operational.
2. **Safe Stdio Transport**: All internal logging is piped exclusively to `sys.stderr`. `stdout` is reserved strictly for JSON-RPC message framing to avoid parsing corruptions.
3. **Session Scoping**: All database queries use bounded `try...finally: db.close()` blocks, preventing connection pool exhaustion in PostgreSQL.
4. **Tool Exception Boundaries**: Every tool function catches internal exceptions and returns human-readable diagnostic messages to the model instead of raising fatal uncaught exceptions.

---

## 2. Capabilities Exposed via MCP

### A. Resources
- `reposage://repositories`: Read-only list of all indexed repositories, statuses, file counts, and language breakdowns.
- `reposage://repository/{repository_id}/files`: File directory tree with AST chunk counts and line totals.

### B. Tools
- `list_repositories`: Discovers indexed repositories and their UUIDs.
- `search_codebase(repository_id, query, search_type, top_k, file_filter)`: Runs hybrid (pgvector dense + PostgreSQL FTS) code retrieval with AST symbol boosting.
- `review_code(repository_id, file_path, code_snippet)`: Audits code across 6 dimensions: potential bugs, null safety, exceptions, security, performance, and maintainability.
- `diagnose_error(repository_id, error_message, stack_trace, relevant_file)`: Analyzes stack traces, diagnoses root cause, and generates unified git diff patches.
- `ask_codebase(repository_id, question)`: Grounded question-answering with exact line-range citations.

### C. Prompts
- `debug_workflow(error_message, stack_trace)`: Step-by-step interactive debugging prompt.
- `code_review_workflow(repository_id, file_path)`: Production code quality and security audit workflow.

---

## 3. How to Connect to AI Clients

### Option A: Cursor IDE
Add to your project's `.cursor/mcp.json` (or global Cursor Settings -> Features -> MCP):

```json
{
  "mcpServers": {
    "reposage": {
      "command": "python",
      "args": ["backend/mcp_server.py"],
      "env": {
        "PYTHONPATH": "backend"
      }
    }
  }
}
```

### Option B: Claude Desktop
Add to your `claude_desktop_config.json` (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "reposage": {
      "command": "C:\\Users\\<USER>\\Documents\\Repo Sage\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\<USER>\\Documents\\Repo Sage\\backend\\mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\<USER>\\Documents\\Repo Sage\\backend"
      }
    }
  }
}
```

### Option C: Remote / HTTP Clients (SSE Transport)
To run the MCP server over HTTP Server-Sent Events (SSE) on port 8001:

```bash
make mcp-sse
# or directly:
PYTHONPATH=backend python backend/mcp_server.py --transport sse --port 8001
```
The SSE endpoint will be available at `http://127.0.0.1:8001/sse`.

---

## 4. Verification

Run the test verification suite to ensure all tools and resources are registered properly:

```bash
python -c "import asyncio; from backend.mcp_server import mcp; asyncio.run(mcp.list_tools())"
```
