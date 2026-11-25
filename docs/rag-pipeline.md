# RepoSage RAG & Hybrid Retrieval Pipeline

The central GenAI mechanism of RepoSage is designed to eliminate hallucinated answers and provide verifiable code intelligence.

## 1. Code-Aware Ingestion Pipeline

Blindly slicing files into fixed character windows breaks function signatures and strips docstrings from class bodies. RepoSage uses hierarchical symbol chunking:

1. **AST Extraction**:
   - Parses AST trees for Python.
   - Extracts top-level functions, classes, methods, docstrings, and line ranges.
   - Regex/heuristic symbol parser extracts signatures for JS/TS, Java, Go, Rust, and C++.
2. **Context Preservation**:
   - Large functions exceeding `MAX_CHUNK_SIZE` (1,200 chars) are broken into overlapping chunks while **retaining the function signature header** at the top of every chunk.
   - Non-symbol code (module-level constants, decorators, imports) is grouped into module-scope chunks.
3. **Chunk Metadata**:
   Each chunk stores `file_path`, `symbol_name`, `symbol_type`, `start_line`, `end_line`, and `language`.

---

## 2. Hybrid Retrieval with Reciprocal Rank Fusion (RRF)

Vector search excels at conceptual similarities (e.g., finding where "session expiration" is handled), but struggles with exact identifiers like `calculate_tax_v2` or `HTTP_401_UNAUTHORIZED`.

RepoSage combines dense vector embeddings with full-text keyword retrieval using **Reciprocal Rank Fusion**:

$$Score_{RRF}(d) = \sum_{m \in M} \frac{w_m}{k + \text{rank}_m(d)}$$

Where:
- $k = 60$ (smoothing constant preventing high-rank domination)
- $w_{\text{dense}} = 1.0$ (cosine similarity vector score)
- $w_{\text{keyword}} = 1.0$ (token overlap in content and file path)
- $w_{\text{symbol}} = 1.5$ (boost for chunks whose symbol matches query tokens)

---

## 3. Grounded Answer Generation & Citation Validation

The LLM is governed by strict system prompts instructing it to cite only verified line ranges and never invent files or line numbers.

Before returning an answer to the developer:
1. The structured Pydantic payload is validated.
2. Every cited file path is checked against `repository_files` table.
3. If an invalid or hallucinated file is cited, it is filtered out and replaced with the confirmed top-ranked chunk.
4. The frontend renders source pills that open Monaco Editor directly to the referenced lines.
