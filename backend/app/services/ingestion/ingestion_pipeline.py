import hashlib
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk
from app.models.symbol import Symbol
from app.models.ingestion_job import IngestionJob
from app.core.config import settings
from app.services.ingestion.filter import should_index_file, detect_language
from app.services.parsing.parser import SymbolParser, ParsedFileStructure
from app.services.chunking.code_chunker import CodeChunker, RawChunk
from app.services.embeddings.provider import get_embedding_provider
from app.services.retrieval.qdrant_service import get_qdrant_service

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Incremental repository indexing engine.
    - Discovers indexable code files with security & binary exclusions.
    - Compares content hashes to skip unchanged files and cleanly purge deleted/modified files.
    - Performs Tree-sitter AST parsing to extract symbols, decorators, and imports.
    - Generates code-aware chunks preserving language boundaries.
    - Persists metadata & symbols to PostgreSQL.
    - Upserts dense vector embeddings to Qdrant collection with repository/file payloads.
    """
    def __init__(self, db: Session, repository: Repository, job: Optional[IngestionJob] = None):
        self.db = db
        self.repo = repository
        self.job = job
        self.chunker = CodeChunker()
        self.embedder = get_embedding_provider()
        self.qdrant = get_qdrant_service()

    def _update_job(self, progress: int, stage: str, error: Optional[str] = None):
        if self.job:
            self.job.progress = progress
            self.job.current_stage = stage
            if error:
                self.job.status = "failed"
                self.job.error_message = error
                self.job.completed_at = datetime.now(timezone.utc)
            self.db.commit()

    def run(self) -> Tuple[int, int]:
        """
        Execute repository ingestion and indexing.
        Returns (total_files_indexed, total_chunks_indexed).
        """
        logger.info(f"Starting ingestion pipeline for repository {self.repo.id} ({self.repo.name})")
        self.repo.status = "indexing"
        self.db.commit()

        try:
            repo_path = Path(self.repo.local_path).resolve()
            if not repo_path.exists():
                raise FileNotFoundError(f"Repository local path '{repo_path}' does not exist.")

            # Stage 1: File Discovery & Filtering
            self._update_job(15, "file_discovery")
            max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            discovered_paths: List[Path] = []
            language_counts: Dict[str, int] = {}

            for root, dirs, files in os.walk(repo_path):
                # Exclude unwanted directories
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d not in (
                        "node_modules", "vendor", "dist", "build", "__pycache__",
                        ".venv", "venv", ".git", "target", "bin", "obj", ".idea", ".vscode"
                    )
                ]
                for file_name in files:
                    file_p = Path(root) / file_name
                    if should_index_file(file_p, max_bytes):
                        discovered_paths.append(file_p)

            logger.info(f"Discovered {len(discovered_paths)} indexable files in {self.repo.name}")

            # Stage 2: Incremental File Hashing & Diff Detection
            self._update_job(30, "incremental_diff")
            existing_files = {
                f.file_path: f
                for f in self.db.query(RepositoryFile).filter(RepositoryFile.repository_id == self.repo.id).all()
            }

            current_file_hashes: Dict[str, Tuple[Path, str, str, int]] = {}
            for file_p in discovered_paths:
                rel_path = str(file_p.relative_to(repo_path)).replace("\\", "/")
                lang = detect_language(file_p)
                try:
                    with open(file_p, "rb") as f:
                        file_bytes = f.read()
                    content_hash = hashlib.sha256(file_bytes).hexdigest()
                    file_size = len(file_bytes)
                    current_file_hashes[rel_path] = (file_p, lang, content_hash, file_size)
                    language_counts[lang] = language_counts.get(lang, 0) + 1
                except Exception as read_err:
                    logger.warning(f"Failed to read file {file_p}: {read_err}")

            # Determine deleted, modified, and added files
            current_rel_paths = set(current_file_hashes.keys())
            existing_rel_paths = set(existing_files.keys())

            deleted_paths = existing_rel_paths - current_rel_paths
            for del_path in deleted_paths:
                rf = existing_files[del_path]
                self.qdrant.delete_file_vectors(self.repo.id, del_path)
                self.db.delete(rf)
            if deleted_paths:
                self.db.commit()
                logger.info(f"Cleaned up {len(deleted_paths)} deleted files from index.")

            files_to_process: List[Tuple[Path, str, str, int, Optional[RepositoryFile]]] = []
            unchanged_files_count = 0

            for rel_path, (file_p, lang, content_hash, file_size) in current_file_hashes.items():
                if rel_path in existing_files:
                    existing_rf = existing_files[rel_path]
                    if existing_rf.content_hash == content_hash:
                        unchanged_files_count += 1
                        continue  # File unchanged, skip re-chunking
                    else:
                        # File modified: purge stale chunks & symbols
                        self.qdrant.delete_file_vectors(self.repo.id, rel_path)
                        self.db.query(CodeChunk).filter(CodeChunk.file_id == existing_rf.id).delete()
                        self.db.query(Symbol).filter(Symbol.file_id == existing_rf.id).delete()
                        self.db.commit()
                        files_to_process.append((file_p, lang, content_hash, file_size, existing_rf))
                else:
                    # New file
                    files_to_process.append((file_p, lang, content_hash, file_size, None))

            logger.info(
                f"Indexing breakdown: {len(files_to_process)} files to parse/chunk, "
                f"{unchanged_files_count} unchanged files preserved."
            )

            # Stage 3: AST Parsing, Symbol Extraction, and Code-Aware Chunking
            self._update_job(50, "code_chunking_and_symbols")
            all_chunks_to_embed: List[Tuple[RepositoryFile, RawChunk]] = []
            commit_sha = self.repo.commit_sha or "HEAD"

            for file_p, lang, content_hash, file_size, existing_rf in files_to_process:
                try:
                    rel_path = str(file_p.relative_to(repo_path)).replace("\\", "/")
                    with open(file_p, "r", encoding="utf-8", errors="replace") as f:
                        text_content = f.read()

                    if existing_rf:
                        rf = existing_rf
                        rf.content_hash = content_hash
                        rf.file_size = file_size
                        rf.language = lang
                        rf.indexed_at = datetime.now(timezone.utc)
                    else:
                        rf = RepositoryFile(
                            repository_id=self.repo.id,
                            file_path=rel_path,
                            language=lang,
                            content_hash=content_hash,
                            file_size=file_size
                        )
                        self.db.add(rf)
                    self.db.commit()
                    self.db.refresh(rf)

                    # Tree-sitter AST structure & symbol extraction
                    parsed_structure: ParsedFileStructure = SymbolParser.parse_file(text_content, lang)
                    for sym in parsed_structure.symbols:
                        sym_model = Symbol(
                            repository_id=self.repo.id,
                            file_id=rf.id,
                            name=sym.name,
                            symbol_type=sym.symbol_type,
                            parent_name=sym.parent_name,
                            start_line=sym.start_line,
                            end_line=sym.end_line,
                            docstring=sym.docstring
                        )
                        sym_model.decorators = sym.decorators
                        sym_model.dependencies = sym.dependencies
                        self.db.add(sym_model)

                    # Extract AST code chunks
                    raw_chunks = self.chunker.chunk_file(text_content, rel_path, lang, commit_sha=commit_sha)
                    for rc in raw_chunks:
                        all_chunks_to_embed.append((rf, rc))

                except Exception as e:
                    logger.warning(f"Error during parsing/chunking file {file_p}: {e}")

            self.db.commit()

            # Stage 4: Embedding Generation & Vector Storage (Qdrant + PostgreSQL)
            self._update_job(70, "embedding_generation")
            logger.info(f"Generating embeddings for {len(all_chunks_to_embed)} chunks")

            batch_size = settings.EMBEDDING_BATCH_SIZE
            chunk_models: List[CodeChunk] = []
            qdrant_payloads: List[Dict[str, Any]] = []

            for i in range(0, len(all_chunks_to_embed), batch_size):
                batch = all_chunks_to_embed[i:i + batch_size]
                texts = [
                    f"File: {rf.file_path} Symbol: {rc.symbol_name or 'N/A'}\n{rc.content}"
                    for rf, rc in batch
                ]
                embeddings = self.embedder.embed_batch(texts)

                for (rf, rc), emb in zip(batch, embeddings):
                    chunk_obj = CodeChunk(
                        repository_id=self.repo.id,
                        file_id=rf.id,
                        content=rc.content,
                        symbol_name=rc.symbol_name,
                        symbol_type=rc.symbol_type,
                        start_line=rc.start_line,
                        end_line=rc.end_line,
                        language=rc.language
                    )
                    chunk_obj.embedding = emb
                    chunk_obj.chunk_metadata = {
                        "file_path": rf.file_path,
                        "chunk_type": rc.chunk_type,
                        **rc.metadata
                    }
                    chunk_models.append(chunk_obj)
                    self.db.add(chunk_obj)

            self.db.commit()
            for ch in chunk_models:
                self.db.refresh(ch)
                qdrant_payloads.append({
                    "id": ch.id,
                    "embedding": ch.embedding,
                    "content": ch.content,
                    "file_path": ch.chunk_metadata.get("file_path", ""),
                    "symbol_name": ch.symbol_name,
                    "symbol_type": ch.symbol_type,
                    "start_line": ch.start_line,
                    "end_line": ch.end_line,
                    "language": ch.language,
                    "chunk_type": ch.chunk_metadata.get("chunk_type", "symbol"),
                    "content_hash": ch.chunk_metadata.get("content_hash", "")
                })

            # Stage 5: Upsert to Qdrant Vector DB
            self._update_job(88, "storing_vectors_in_qdrant")
            if qdrant_payloads:
                self.qdrant.upsert_chunks(self.repo.id, qdrant_payloads)

            # Stage 6: Update Repository Summary Metadata
            total_active_files = self.db.query(RepositoryFile).filter(RepositoryFile.repository_id == self.repo.id).count()
            total_active_chunks = self.db.query(CodeChunk).filter(CodeChunk.repository_id == self.repo.id).count()

            primary_lang = "Generic"
            if language_counts:
                code_langs = {k: v for k, v in language_counts.items() if k not in ("json", "yaml", "markdown", "dockerfile")}
                target_map = code_langs if code_langs else language_counts
                primary_lang = max(target_map.items(), key=lambda x: x[1])[0]

            self.repo.status = "ready"
            self.repo.primary_language = primary_lang
            self.repo.total_files = total_active_files
            self.repo.total_chunks = total_active_chunks
            self.repo.last_indexed_at = datetime.now(timezone.utc)
            self.repo.error_message = None

            if self.job:
                self.job.status = "completed"
                self.job.progress = 100
                self.job.current_stage = "ready"
                self.job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            logger.info(
                f"Indexing finished successfully for {self.repo.name}: "
                f"{total_active_files} files, {total_active_chunks} chunks."
            )
            return total_active_files, total_active_chunks

        except Exception as e:
            logger.exception(f"Ingestion failed for repo {self.repo.id}: {e}")
            self.repo.status = "failed"
            self.repo.error_message = str(e)
            self._update_job(0, "failed", error=str(e))
            self.db.commit()
            raise
