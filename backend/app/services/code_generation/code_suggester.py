import re
import difflib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_change import CodeChange
from app.models.user import User
from app.schemas.code import CodeSuggestRequest, CodeSuggestResponse, DiffChangeResponse
from app.services.repository.repo_service import RepositoryService
from app.services.rag.llm_provider import get_llm_provider
from app.core.exceptions import EntityNotFoundException, RepoSageException

logger = logging.getLogger(__name__)


def apply_unified_diff(original_text: str, diff_text: str) -> str:
    """
    Pure Python unified diff applier for single-file patches.
    Parses hunks and applies line additions and deletions deterministically.
    """
    lines = original_text.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)

    hunk_pattern = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

    hunks = []
    current_hunk = None
    for line in diff_lines:
        m = hunk_pattern.match(line)
        if m:
            if current_hunk:
                hunks.append(current_hunk)
            orig_start = int(m.group(1))
            orig_len = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_len = int(m.group(4)) if m.group(4) is not None else 1
            current_hunk = {
                "orig_start": orig_start,
                "orig_len": orig_len,
                "new_start": new_start,
                "new_len": new_len,
                "lines": []
            }
        elif current_hunk is not None:
            if line.startswith(("+", "-", " ", "\\")):
                current_hunk["lines"].append(line)
    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        return original_text

    result_lines = list(lines)
    for hunk in reversed(hunks):
        start_idx = max(0, hunk["orig_start"] - 1)
        orig_count = hunk["orig_len"]

        replacement = []
        for hl in hunk["lines"]:
            if hl.startswith("+"):
                text = hl[1:]
                if not text.endswith("\n"):
                    text += "\n"
                replacement.append(text)
            elif hl.startswith(" "):
                replacement.append(hl[1:])

        result_lines[start_idx:start_idx + orig_count] = replacement

    return "".join(result_lines)


class CodeSuggesterService:
    def __init__(self, db: Session, repository_id: str):
        self.db = db
        self.repository_id = repository_id
        self.llm = get_llm_provider()

    def generate_suggestion(self, req: CodeSuggestRequest, user: User) -> CodeSuggestResponse:
        """
        Generate AI code improvement/refactoring and compute a clean unified git diff.
        Does NOT apply changes automatically; creates a pending CodeChange record.
        """
        repo = self.db.query(Repository).filter(Repository.id == self.repository_id).first()
        if not repo:
            raise EntityNotFoundException("Repository", self.repository_id)

        original_code, ext, line_count, _ = RepositoryService.get_file_content(
            self.db, self.repository_id, req.file_path
        )

        system_prompt = (
            "You are RepoSage Code Assistant. Given source code and user instruction, generate the improved or refactored "
            "code. Return ONLY the full updated code for the file without surrounding conversational remarks."
        )

        user_content = (
            f"File: {req.file_path}\n"
            f"Instruction: {req.instruction}\n\n"
            f"Original Code:\n```\n{original_code}\n```"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        llm_res = self.llm.generate(messages)
        suggested_code = llm_res.content.strip()

        # Clean code fence if present
        if suggested_code.startswith("```"):
            lines = suggested_code.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            suggested_code = "\n".join(lines)

        # Generate unified diff
        orig_lines = original_code.splitlines(keepends=True)
        new_lines = [line + "\n" if not line.endswith("\n") else line for line in suggested_code.splitlines()]
        
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{req.file_path}",
            tofile=f"b/{req.file_path}",
            lineterm=""
        )
        unified_diff_str = "".join(diff)
        if not unified_diff_str:
            unified_diff_str = f"# No textual changes between original and suggestion for {req.file_path}"

        # Persist pending CodeChange
        code_change = CodeChange(
            repository_id=self.repository_id,
            user_id=user.id,
            original_commit_sha=repo.commit_sha or "HEAD",
            patch_content=unified_diff_str,
            status="pending_review"
        )
        self.db.add(code_change)
        self.db.commit()
        self.db.refresh(code_change)

        return CodeSuggestResponse(
            repository_id=self.repository_id,
            file_path=req.file_path,
            instruction=req.instruction,
            explanation="Generated refactoring aligned with your instructions. Review diff before approval.",
            unified_diff=unified_diff_str,
            original_code=original_code,
            suggested_code=suggested_code,
            change_id=code_change.id
        )

    def apply_approved_change(self, change_id: str, user: User, target_path_override: Optional[str] = None) -> CodeChange:
        """
        Human approval workflow:
        Verifies pending change, validates file target, and safely applies the approved modification
        directly to the repository workspace files.
        """
        change = self.db.query(CodeChange).filter(
            CodeChange.id == change_id,
            CodeChange.repository_id == self.repository_id,
            CodeChange.user_id == user.id
        ).first()

        if not change:
            raise EntityNotFoundException("CodeChange", change_id)

        if change.status == "applied":
            return change

        repo = self.db.query(Repository).filter(Repository.id == self.repository_id).first()
        if not repo or not repo.local_path:
            raise RepoSageException("Repository workspace unavailable.")

        # Determine target file path
        target_path = target_path_override
        if not target_path:
            m = re.search(r"^\+\+\+\s+(?:b/)?([^\r\n]+)", change.patch_content, re.MULTILINE)
            if not m:
                m = re.search(r"^---\s+(?:a/)?([^\r\n]+)", change.patch_content, re.MULTILINE)
            if m:
                target_path = m.group(1).strip()

        if not target_path:
            raise RepoSageException("Could not determine target file path for diff application.")

        base_dir = Path(repo.local_path).resolve()
        target_file = (base_dir / target_path).resolve()

        # Path traversal guard
        try:
            target_file.relative_to(base_dir)
        except ValueError:
            raise RepoSageException("Access denied: File path escapes repository workspace.")

        if target_file.is_file():
            try:
                original_content = target_file.read_text(encoding="utf-8", errors="replace")
                new_content = apply_unified_diff(original_content, change.patch_content)
                target_file.write_text(new_content, encoding="utf-8")
            except Exception as e:
                raise RepoSageException(f"Failed to apply patch to file: {e}")
        else:
            # File does not exist yet; assemble added lines
            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                new_lines = [
                    l[1:] for l in change.patch_content.splitlines(keepends=True)
                    if l.startswith("+") and not l.startswith("+++")
                ]
                new_content = "".join(new_lines)
                target_file.write_text(new_content, encoding="utf-8")
            except Exception as e:
                raise RepoSageException(f"Failed to create new file from patch: {e}")

        # Update database file entry if registered
        rf = self.db.query(RepositoryFile).filter(
            RepositoryFile.repository_id == self.repository_id,
            RepositoryFile.file_path == target_path
        ).first()
        if rf:
            rf.file_size = len(new_content.encode("utf-8"))

        # Mark as approved and applied
        change.status = "applied"
        change.approved_at = datetime.now(timezone.utc)
        change.applied_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(change)
        return change

    def apply_diff_direct(self, file_path: str, diff_text: str, user: User) -> CodeChange:
        """
        Directly approve and apply a unified diff (e.g., from debugging suggestions)
        by registering a change record and modifying the workspace.
        """
        repo = self.db.query(Repository).filter(Repository.id == self.repository_id).first()
        if not repo:
            raise EntityNotFoundException("Repository", self.repository_id)

        code_change = CodeChange(
            repository_id=self.repository_id,
            user_id=user.id,
            original_commit_sha=repo.commit_sha or "HEAD",
            patch_content=diff_text,
            status="pending_review"
        )
        self.db.add(code_change)
        self.db.commit()
        self.db.refresh(code_change)

        return self.apply_approved_change(code_change.id, user, target_path_override=file_path)
