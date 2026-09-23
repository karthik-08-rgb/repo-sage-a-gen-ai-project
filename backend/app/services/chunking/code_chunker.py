import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from app.services.parsing.parser import CodeSymbol, SymbolParser, ParsedFileStructure
from app.core.config import settings


@dataclass
class RawChunk:
    content: str
    symbol_name: Optional[str]
    symbol_type: Optional[str]  # function, class, method, module, interface, struct
    start_line: int
    end_line: int
    language: str
    chunk_type: str = "symbol"  # symbol, sub_chunk, module_header, module_scope
    content_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class CodeChunker:
    """
    Code-aware chunker utilizing Tree-sitter AST parsing.
    Preserves class/function boundaries, imports, and symbol parentage.
    Intelligently sub-chunks oversized functions with contextual headers.
    """
    def __init__(
        self,
        max_chunk_size: int = settings.MAX_CHUNK_SIZE,
        overlap: int = settings.CHUNK_OVERLAP
    ):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_file(
        self,
        content: str,
        file_path: str,
        language: str,
        commit_sha: Optional[str] = None
    ) -> List[RawChunk]:
        """
        Split source code into AST code-aware chunks preserving symbols, boundaries, and line numbers.
        """
        lines = content.splitlines(keepends=True)
        if not lines:
            return []

        # Parse AST structure using Tree-sitter
        parsed_structure: ParsedFileStructure = SymbolParser.parse_file(content, language)
        symbols = parsed_structure.symbols
        imports_header = "\n".join(parsed_structure.imports[:15]) if parsed_structure.imports else ""

        chunks: List[RawChunk] = []
        covered_lines: Set[int] = set()

        # Sort symbols: top-level first, then nested methods
        valid_symbols = [s for s in symbols if s.end_line >= s.start_line]

        for sym in valid_symbols:
            s_idx = max(0, sym.start_line - 1)
            e_idx = min(len(lines), sym.end_line)
            sym_lines = lines[s_idx:e_idx]
            sym_text = "".join(sym_lines).strip()
            if not sym_text:
                continue

            for l_no in range(sym.start_line, sym.end_line + 1):
                covered_lines.add(l_no)

            common_metadata = {
                "file_path": file_path,
                "parent_symbol": sym.parent_name,
                "docstring": sym.docstring,
                "decorators": sym.decorators,
                "commit_sha": commit_sha or "HEAD"
            }

            if len(sym_text) <= self.max_chunk_size:
                # Intact symbol chunk preserving complete boundary
                chunks.append(RawChunk(
                    content=sym_text,
                    symbol_name=sym.name,
                    symbol_type=sym.symbol_type,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    language=language,
                    chunk_type="symbol",
                    metadata=common_metadata
                ))
            else:
                # Oversized symbol: intelligently sub-chunk with definition signature header
                sig_header = sym_lines[0].strip() if sym_lines else ""
                if sym.decorators:
                    sig_header = f"{' '.join(sym.decorators)} {sig_header}"

                prefix = f"// Context: {file_path} > {sym.name} ({sym.symbol_type})\n{sig_header}\n" if language != "python" else f"# Context: {file_path} > {sym.name} ({sym.symbol_type})\n{sig_header}\n"

                sub_chunks = self._chunk_lines(
                    lines=sym_lines,
                    start_line_offset=sym.start_line,
                    prefix=prefix,
                    symbol_name=sym.name,
                    symbol_type=sym.symbol_type,
                    file_path=file_path,
                    language=language,
                    extra_metadata=common_metadata
                )
                chunks.extend(sub_chunks)

        # Extract uncovered code blocks (imports, module-level variables, configurations)
        uncovered_chunks = self._extract_uncovered_ranges(
            lines=lines,
            covered_lines=covered_lines,
            file_path=file_path,
            language=language,
            commit_sha=commit_sha
        )
        chunks.extend(uncovered_chunks)

        # Sort chunks strictly by starting line
        chunks.sort(key=lambda c: (c.start_line, c.end_line))
        return chunks

    def _chunk_lines(
        self,
        lines: List[str],
        start_line_offset: int,
        prefix: str,
        symbol_name: Optional[str],
        symbol_type: str,
        file_path: str,
        language: str,
        extra_metadata: Dict[str, Any]
    ) -> List[RawChunk]:
        """Split a large symbol's lines into overlapping sub-chunks retaining contextual header."""
        chunks: List[RawChunk] = []
        n_lines = len(lines)
        if n_lines == 0:
            return chunks

        current_lines: List[str] = []
        current_chars = len(prefix)
        chunk_start = 1

        for i, line in enumerate(lines, start=1):
            if not current_lines:
                chunk_start = i

            current_lines.append(line)
            current_chars += len(line)

            if current_chars >= self.max_chunk_size and len(current_lines) > 1:
                content = (prefix + "".join(current_lines)).strip()
                chunks.append(RawChunk(
                    content=content,
                    symbol_name=symbol_name,
                    symbol_type=symbol_type,
                    start_line=start_line_offset + chunk_start - 1,
                    end_line=start_line_offset + i - 1,
                    language=language,
                    chunk_type="sub_chunk",
                    metadata=dict(extra_metadata)
                ))

                # Step back for overlap
                overlap_chars = 0
                step_back_idx = len(current_lines)
                for rev_idx in range(len(current_lines) - 1, -1, -1):
                    overlap_chars += len(current_lines[rev_idx])
                    if overlap_chars >= self.overlap:
                        step_back_idx = rev_idx
                        break

                current_lines = current_lines[step_back_idx:]
                current_chars = len(prefix) + sum(len(l) for l in current_lines)
                chunk_start = i - len(current_lines) + 1

        if current_lines:
            content = (prefix + "".join(current_lines)).strip()
            if content:
                chunks.append(RawChunk(
                    content=content,
                    symbol_name=symbol_name,
                    symbol_type=symbol_type,
                    start_line=start_line_offset + chunk_start - 1,
                    end_line=start_line_offset + n_lines - 1,
                    language=language,
                    chunk_type="sub_chunk",
                    metadata=dict(extra_metadata)
                ))

        return chunks

    def _extract_uncovered_ranges(
        self,
        lines: List[str],
        covered_lines: Set[int],
        file_path: str,
        language: str,
        commit_sha: Optional[str]
    ) -> List[RawChunk]:
        """Extract continuous ranges of lines not inside recognized symbols (e.g., imports, globals)."""
        chunks: List[RawChunk] = []
        range_start: Optional[int] = None
        range_lines: List[str] = []

        for line_no, line in enumerate(lines, start=1):
            if line_no not in covered_lines:
                if range_start is None:
                    range_start = line_no
                range_lines.append(line)
            else:
                if range_lines:
                    text = "".join(range_lines).strip()
                    if text:
                        c_type = "module_header" if range_start == 1 else "module_scope"
                        chunks.append(RawChunk(
                            content=text,
                            symbol_name="module_scope",
                            symbol_type="module",
                            start_line=range_start,
                            end_line=line_no - 1,
                            language=language,
                            chunk_type=c_type,
                            metadata={
                                "file_path": file_path,
                                "parent_symbol": None,
                                "commit_sha": commit_sha or "HEAD"
                            }
                        ))
                    range_lines = []
                    range_start = None

        if range_lines:
            text = "".join(range_lines).strip()
            if text:
                c_type = "module_header" if range_start == 1 else "module_scope"
                chunks.append(RawChunk(
                    content=text,
                    symbol_name="module_scope",
                    symbol_type="module",
                    start_line=range_start or 1,
                    end_line=len(lines),
                    language=language,
                    chunk_type=c_type,
                    metadata={
                        "file_path": file_path,
                        "parent_symbol": None,
                        "commit_sha": commit_sha or "HEAD"
                    }
                ))

        return chunks
