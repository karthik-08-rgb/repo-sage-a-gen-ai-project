import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.schemas.review import CodeReviewRequest, CodeReviewResponse, ReviewFinding
from app.services.repository.repo_service import RepositoryService
from app.services.rag.llm_provider import get_llm_provider
from app.core.exceptions import EntityNotFoundException, RepoSageException

logger = logging.getLogger(__name__)


class CodeReviewService:
    def __init__(self, db: Session, repository_id: str):
        self.db = db
        self.repository_id = repository_id
        self.llm = get_llm_provider()

    def review_code(self, req: CodeReviewRequest) -> CodeReviewResponse:
        repo = self.db.query(Repository).filter(Repository.id == self.repository_id).first()
        if not repo:
            raise EntityNotFoundException("Repository", self.repository_id)

        target_name = req.file_path or "provided snippet"
        code_content = req.code_snippet or ""

        # If a file path is provided, read the actual file content
        if req.file_path:
            content, _, _, _ = RepositoryService.get_file_content(self.db, self.repository_id, req.file_path)
            code_content = content

        if not code_content.strip():
            raise RepoSageException("No code content available to review.")

        # Cap length to prevent overflowing LLM context
        max_chars = 15000
        truncated_code = code_content[:max_chars]
        if len(code_content) > max_chars:
            truncated_code += "\n... [truncated for review context] ..."

        system_prompt = (
            "You are RepoSage Code Reviewer, an expert Principal Security & Software Engineer. "
            "Review the submitted source code thoroughly across these dimensions:\n"
            "1. Potential bugs and logical flaws\n"
            "2. Null handling and edge cases\n"
            "3. Exception handling and failure modes\n"
            "4. Security vulnerabilities (injection, SSRF, secret leakage)\n"
            "5. Performance bottlenecks and algorithmic complexity\n"
            "6. Maintainability and naming conventions\n\n"
            "Categorize severity accurately: Critical, High, Medium, Low, Informational. "
            "Do NOT report generic style preferences as confirmed bugs."
        )

        user_content = (
            f"Target: {target_name}\n"
            f"Source Code:\n```\n{truncated_code}\n```\n\n"
            "Return a structured CodeReviewResponse."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            res = self.llm.generate_structured(messages, CodeReviewResponse)
            return res
        except Exception as e:
            logger.warning(f"Structured review failed: {e}. Returning rule-based fallback review.")
            # Fallback static checks
            findings = []
            lines = code_content.splitlines()
            for i, line in enumerate(lines, start=1):
                if "eval(" in line or "exec(" in line:
                    findings.append(ReviewFinding(
                        title="Use of dangerous dynamic execution (eval/exec)",
                        severity="Critical",
                        category="Security",
                        description="Direct dynamic evaluation of strings can cause remote code execution.",
                        evidence=line.strip(),
                        file_path=req.file_path or "snippet",
                        start_line=i,
                        end_line=i,
                        suggested_improvement="Replace eval/exec with safe deterministic parsing logic.",
                        confidence="High"
                    ))
                elif "except:" in line or "except Exception: pass" in line:
                    findings.append(ReviewFinding(
                        title="Silent exception swallowing",
                        severity="Medium",
                        category="ExceptionHandling",
                        description="Blanket exception capture without logging obscures runtime errors.",
                        evidence=line.strip(),
                        file_path=req.file_path or "snippet",
                        start_line=i,
                        end_line=i,
                        suggested_improvement="Log the exception or catch specific expected exception types.",
                        confidence="High"
                    ))

            return CodeReviewResponse(
                repository_id=self.repository_id,
                target=target_name,
                total_findings=len(findings),
                findings=findings,
                summary=f"Automated static audit completed. Found {len(findings)} findings."
            )
