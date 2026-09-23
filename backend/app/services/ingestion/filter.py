import os
from pathlib import Path
from typing import Set

# Directories to ignore unconditionally
IGNORED_DIRECTORIES: Set[str] = {
    ".git", ".svn", ".hg",
    "node_modules", "bower_components",
    "vendor", "packages",
    "dist", "build", "out", "target", "bin", "obj",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".venv", "venv", "env", "ENV", ".tox",
    "coverage", ".nyc_output", "htmlcov",
    ".idea", ".vscode", ".vs",
    ".gemini", ".system_generated"
}

# Sensitive / secret file patterns never to index
SENSITIVE_FILES: Set[str] = {
    ".env", ".env.local", ".env.production", ".env.development", ".env.staging",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials.json", "service-account.json", "client_secret.json",
    "secrets.yaml", "secrets.json",
    ".npmrc", ".pypirc", ".dockercfg"
}

# Binary and non-code file extensions to ignore
IGNORED_EXTENSIONS: Set[str] = {
    # Binaries & executables
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".msi", ".class", ".pyc", ".pyo",
    # Archives
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz",
    # Media & Images
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp", ".tiff",
    ".mp3", ".wav", ".ogg", ".mp4", ".avi", ".mkv", ".mov",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Lock files with low code semantic value
    ".lock", "-lock.json",
    # Large data / documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".tsv", ".parquet", ".sqlite", ".db"
}

# File extensions mapped to languages
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".dockerfile": "dockerfile"
}


def is_ignored_directory(dir_name: str) -> bool:
    return dir_name in IGNORED_DIRECTORIES or dir_name.startswith(".")


def is_sensitive_file(file_name: str) -> bool:
    name_lower = file_name.lower()
    if name_lower in SENSITIVE_FILES or name_lower.startswith(".env"):
        return True
    if any(name_lower.endswith(ext) for ext in [".key", ".pem", ".p12", ".pfx", ".keystore"]):
        return True
    return False


def should_index_file(file_path: Path, max_size_bytes: int) -> bool:
    """Determine whether a file should be indexed based on filtering rules."""
    file_name = file_path.name
    
    # Check sensitive
    if is_sensitive_file(file_name):
        return False

    # Check extension
    suffix = file_path.suffix.lower()
    if suffix in IGNORED_EXTENSIONS:
        return False

    # Check path parts for ignored directories
    for part in file_path.parts[:-1]:
        if part in IGNORED_DIRECTORIES:
            return False

    # Check file size if file exists on disk
    if file_path.exists():
        try:
            stat_res = file_path.stat()
            if stat_res.st_size > max_size_bytes or stat_res.st_size == 0:
                return False
        except OSError:
            return False

    return True


def detect_language(file_path: Path) -> str:
    """Detect programming language from file extension or filename."""
    name_lower = file_path.name.lower()
    if name_lower == "dockerfile" or name_lower.endswith(".dockerfile"):
        return "dockerfile"
    if name_lower == "makefile":
        return "makefile"
    return EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower(), "text")
