"""
backend/mcp_server.py
Model Context Protocol (MCP) Server for RepoSage.

Provides standard MCP resources, tools, and prompts for:
- Hybrid codebase search (dense vector similarity + PostgreSQL full-text search)
- AI-driven code review across 6 dimensions
- AI stack trace analysis & unified diff generation
- Grounded Q&A with AST line citations

Transport Options:
- stdio (default): For Claude Desktop, Cursor, Antigravity, or other local IDE plugins.
- sse: For remote or HTTP-based MCP clients (runs on http://127.0.0.1:8001 by default).
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure backend directory is in sys.path even when invoked from outside
backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# CRITICAL FOR STDIO TRANSPORT:
# Redirect all application logging to stderr so stdout is reserved exclusively for JSON-RPC messages.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("reposage-mcp")

# Import MCP Server (compatible with both mcp 2.x and 1.x)
try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

# Import RepoSage core services & database
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk
from app.models.user import User
from app.services.retrieval.retriever import HybridRetriever
from app.services.code_review.reviewer import CodeReviewService
from app.schemas.review import CodeReviewRequest
from app.services.debugging.debugger import DebuggerService
from app.schemas.debug import DebugAnalyzeRequest
from app.services.rag.rag_service import RAGService

# Initialize the MCP Server instance
mcp = MCPServer(
    name="RepoSage Assistant",
    description="Understand, Debug, and Navigate Any Codebase with AI via RepoSage MCP."
)


# ==============================================================================
# RESOURCES
# ==============================================================================

@mcp.resource("reposage://repositories")
def list_repositories_resource() -> str:
    """Read-only resource listing all indexed repositories with statistics."""
    db = SessionLocal()
    try:
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        if not repos:
            return "No repositories have been indexed in RepoSage yet."

        lines = ["# RepoSage Indexed Repositories\n"]
        for repo in repos:
            files = db.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
            file_count = len(files)
            langs = sorted({f.language for f in files if f.language})
            if not langs and repo.primary_language:
                langs = [repo.primary_language]
            lines.append(
                f"- **{repo.name}**\n"
                f"  - ID: `{repo.id}`\n"
                f"  - Status: {repo.status}\n"
                f"  - Indexed Files: {file_count}\n"
                f"  - Languages: {', '.join(langs) if langs else 'N/A'}\n"
                f"  - Source URL: {repo.source_url or 'Local Upload'}\n"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error reading repositories resource: {e}", exc_info=True)
        return f"Error retrieving repositories: {str(e)}"
    finally:
        db.close()


@mcp.resource("reposage://repository/{repository_id}/files")
def list_repository_files_resource(repository_id: str) -> str:
    """Read-only resource listing files indexed for a specific repository."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return f"Repository with ID '{repository_id}' not found."

        files = (
            db.query(RepositoryFile)
            .filter(RepositoryFile.repository_id == repository_id)
            .order_by(RepositoryFile.file_path)
            .all()
        )
        if not files:
            return f"No indexed files found for repository '{repo.name}' ({repository_id})."

        chunk_counts = dict(
            db.query(CodeChunk.file_id, func.count(CodeChunk.id))
            .filter(CodeChunk.repository_id == repository_id)
            .group_by(CodeChunk.file_id)
            .all()
        )

        lines = [f"# Files in {repo.name} ({len(files)} total)\n"]
        for f in files:
            lang = f.language or "text"
            chunks_n = chunk_counts.get(f.id, 0)
            lines.append(f"- `{f.file_path}` ({lang}, {f.file_size} bytes, {chunks_n} AST chunks)")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error reading repository files: {e}", exc_info=True)
        return f"Error reading files for repository {repository_id}: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# TOOLS
# ==============================================================================

@mcp.tool()
def list_repositories() -> str:
    """
    List all repositories indexed in RepoSage.
    Use this tool first to discover repository IDs needed for search, review, or debugging.
    """
    db = SessionLocal()
    try:
        repos = db.query(Repository).all()
        if not repos:
            return "No repositories found in RepoSage database. Index a repository first using the web interface or API."

        output = ["Available RepoSage Repositories:"]
        for r in repos:
            file_count = db.query(RepositoryFile).filter(RepositoryFile.repository_id == r.id).count()
            output.append(f"• Name: {r.name} | ID: {r.id} | Status: {r.status} | Files: {file_count}")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"list_repositories tool failed: {e}", exc_info=True)
        return f"Failed to list repositories: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def search_codebase(
    repository_id: str,
    query: str,
    search_type: str = "hybrid",
    top_k: int = 5,
    file_filter: Optional[str] = None
) -> str:
    """
    Search the codebase using RepoSage's hybrid retrieval engine.
    Combines dense vector embeddings with PostgreSQL Full-Text Search and AST symbol boosting.

    Args:
        repository_id: The UUID of the repository.
        query: Search query, function/class name, or natural language question.
        search_type: Search strategy: 'hybrid' (recommended), 'dense', 'keyword', or 'symbol'.
        top_k: Number of relevant code chunks to return (default: 5).
        file_filter: Optional substring to filter matching file paths (e.g., 'backend/app').
    """
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return f"Error: Repository '{repository_id}' does not exist in RepoSage database."

        retriever = HybridRetriever(db, repository_id=repository_id)
        results = retriever.search(
            query=query,
            search_type=search_type,
            top_k=top_k,
            file_filter=file_filter
        )

        if not results:
            return f"No code snippets found matching '{query}' in repository '{repo.name}'."

        formatted_chunks = [f"Found {len(results)} relevant code snippets in '{repo.name}':\n"]
        for i, r in enumerate(results, start=1):
            symbol = f" | Symbol: `{r.symbol_name}` ({r.symbol_type})" if r.symbol_name else ""
            formatted_chunks.append(
                f"### Result {i}: {r.file_path} (Lines {r.start_line}-{r.end_line})\n"
                f"- Retrieval Score: {r.score:.3f} via {r.retrieval_method}{symbol}\n"
                f"```{r.language or ''}\n"
                f"{r.content}\n"
                f"```"
            )

        return "\n\n".join(formatted_chunks)

    except Exception as e:
        logger.error(f"search_codebase tool error: {e}", exc_info=True)
        return f"Code search failed: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def review_code(
    repository_id: str,
    file_path: Optional[str] = None,
    code_snippet: Optional[str] = None
) -> str:
    """
    Run RepoSage's 6-dimensional AI code reviewer.
    Analyzes code for:
    1. Potential bugs and logic errors
    2. Null safety & edge cases
    3. Exception handling & recovery
    4. Security vulnerabilities (SSRF, injection, credentials)
    5. Performance bottlenecks
    6. Maintainability and design quality

    Args:
        repository_id: The UUID of the repository.
        file_path: Relative path to an indexed repository file to review (e.g., 'backend/app/main.py').
        code_snippet: Optional raw code snippet to review directly instead of a file.
    """
    if not file_path and not code_snippet:
        return "Error: You must provide either a 'file_path' or a 'code_snippet' to review."

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return f"Error: Repository '{repository_id}' not found."

        reviewer = CodeReviewService(db, repository_id=repository_id)
        req = CodeReviewRequest(
            repository_id=repository_id,
            file_path=file_path,
            code_snippet=code_snippet
        )
        response = reviewer.review_code(req)

        output = [
            f"# Code Review Report for: `{response.target}`",
            f"**Repository**: {repo.name}",
            f"**Total Findings**: {response.total_findings}\n",
            f"### Executive Summary\n{response.summary}\n",
            "### Detailed Findings"
        ]

        if not response.findings:
            output.append("No critical issues, security vulnerabilities, or bugs identified. Code looks clean!")
        else:
            for i, f in enumerate(response.findings, start=1):
                loc = f" (Lines {f.start_line}-{f.end_line})" if f.start_line else ""
                output.append(
                    f"\n#### {i}. [{f.severity.upper()}] {f.title}\n"
                    f"- **Category**: {f.category}\n"
                    f"- **Location**: `{f.file_path}`{loc}\n"
                    f"- **Description**: {f.description}\n"
                    f"- **Evidence**: `{f.evidence}`\n"
                    f"- **Suggested Fix**: {f.suggested_improvement}\n"
                    f"- **Confidence**: {f.confidence}"
                )

        return "\n".join(output)

    except Exception as e:
        logger.error(f"review_code tool failed: {e}", exc_info=True)
        return f"Code review failed: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def diagnose_error(
    repository_id: str,
    error_message: str,
    stack_trace: str = "",
    relevant_file: Optional[str] = None
) -> str:
    """
    Diagnose a runtime error or stack trace using RepoSage's AI Debugging Assistant.
    Parses the stack trace, retrieves grounded code chunks, diagnoses the root cause,
    and produces reviewable unified git diff patches.

    Args:
        repository_id: The UUID of the repository.
        error_message: The error string or exception message.
        stack_trace: Optional full multi-line stack trace.
        relevant_file: Optional file path if already suspected.
    """
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return f"Error: Repository '{repository_id}' not found."

        debugger = DebuggerService(db, repository_id=repository_id)
        req = DebugAnalyzeRequest(
            repository_id=repository_id,
            error_message=error_message,
            stack_trace=stack_trace,
            relevant_file=relevant_file
        )
        res = debugger.analyze_error(req)

        output = [
            f"# RepoSage Debug Analysis for {repo.name}\n",
            f"**Error Summary**: {res.error_summary}\n",
            f"### Root Cause Diagnosis\n{res.potential_root_cause}\n",
            f"### Evidence From Codebase\n{res.evidence_from_codebase}\n",
            f"**Affected Files**: {', '.join(res.affected_files) if res.affected_files else 'None detected'}\n"
        ]

        if res.suggested_fixes:
            output.append("### Suggested Fixes & Unified Diffs")
            for idx, fix in enumerate(res.suggested_fixes, start=1):
                output.append(
                    f"\n#### Patch {idx}: `{fix.file_path}` (Confidence: {fix.confidence})\n"
                    f"{fix.description}\n"
                    f"```diff\n{fix.unified_diff}\n```\n"
                    f"**Validation Steps**:\n" + "\n".join([f"- {step}" for step in fix.validation_steps])
                )

        if res.tests_to_validate:
            output.append("\n### Recommended Tests to Run:")
            for t in res.tests_to_validate:
                output.append(f"- `{t}`")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"diagnose_error tool failed: {e}", exc_info=True)
        return f"Debugging analysis failed: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def ask_codebase(repository_id: str, question: str) -> str:
    """
    Ask architectural or implementation questions about an indexed repository.
    Answers are strictly grounded using retrieved AST code chunks with citations.

    Args:
        repository_id: The UUID of the repository.
        question: Question about the architecture, workflow, data models, or endpoints.
    """
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return f"Error: Repository '{repository_id}' not found."

        # Find or create a demo user for grounding attribution
        user = db.query(User).filter(User.email == "demo@reposage.dev").first()
        if not user:
            user = db.query(User).first()

        if not user:
            # Fallback if no user exists in DB: perform hybrid retrieval and summarize
            retriever = HybridRetriever(db, repository_id=repository_id)
            chunks = retriever.search(query=question, top_k=6)
            if not chunks:
                return f"No relevant context found in '{repo.name}' for query '{question}'."
            formatted = [f"Retrieved context for '{question}':\n"]
            for c in chunks:
                formatted.append(f"File: {c.file_path} (Lines {c.start_line}-{c.end_line})\n```\n{c.content}\n```")
            return "\n\n".join(formatted)

        rag = RAGService(db, repository_id=repository_id)
        msg, session = rag.answer_question(question=question, user=user)

        # Build response with citations
        citations_str = ""
        if msg.citations:
            citations_str = "\n\n**Source Citations:**\n" + "\n".join(
                [f"- `{c.get('file_path')}` (Lines {c.get('start_line')}-{c.get('end_line')})" for c in msg.citations]
            )

        return f"{msg.content}{citations_str}"

    except Exception as e:
        logger.error(f"ask_codebase failed: {e}", exc_info=True)
        return f"Ask codebase failed: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# PROMPT TEMPLATES
# ==============================================================================

@mcp.prompt()
def debug_workflow(error_message: str, stack_trace: str = "") -> str:
    """Prompt template guiding an AI model through structured codebase debugging."""
    return f"""You are RepoSage Debugging Assistant.
A runtime error occurred:
Error: {error_message}
Stack Trace:
{stack_trace}

Instructions:
1. Use the `list_repositories` tool to identify the target repository ID if not provided.
2. Use `diagnose_error` with the repository ID and stack trace.
3. If additional context is needed, use `search_codebase` to inspect adjacent modules.
4. Present the root cause and a reviewable unified git diff patch to fix the bug."""


@mcp.prompt()
def code_review_workflow(repository_id: str, file_path: str) -> str:
    """Prompt template for auditing a repository file against production security and quality standards."""
    return f"""You are RepoSage Principal Security & Software Engineer.
Conduct a thorough code review for file: `{file_path}` in repository `{repository_id}`.

Instructions:
1. Call `review_code` with the given repository ID and file path.
2. Analyze the findings across security vulnerabilities, logic flaws, null safety, and performance.
3. Suggest concrete code modifications and tests to prevent regression."""


# ==============================================================================
# SERVER RUNNER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="RepoSage Model Context Protocol (MCP) Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type: 'stdio' for IDEs (Cursor/Claude Desktop), 'sse' for HTTP (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for SSE transport (default: 8001, distinct from FastAPI's 8000)"
    )

    args = parser.parse_args()

    logger.info(f"Starting RepoSage MCP Server with transport='{args.transport}'...")

    if args.transport == "sse":
        logger.info(f"SSE Server will be available at http://{args.host}:{args.port}/sse")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        # stdio transport for IDEs
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
