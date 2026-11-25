# RepoSage Architecture Document

## 1. System Philosophy
RepoSage is designed to solve a core problem in modern software engineering: understanding and navigating large, unfamiliar codebases without losing developer trust to hallucinations. To achieve this, the architecture prioritizes **code-grounded indexing**, **hybrid retrieval (dense vector + full-text RRF)**, and **deterministic citation validation**.

```mermaid
graph TD
    User([Developer / Browser])
    Gateway[Nginx Reverse Proxy / Port 80]
    SPA[React + TypeScript + Monaco Editor]
    API[FastAPI Backend / Uvicorn]
    AuthService[JWT Authentication]
    RepoService[Repository & Security Guard]
    IngestPipeline[Ingestion & Chunking Pipeline]
    Worker[Celery Background Worker]
    RAGEngine[Hybrid Retrieval & Agent Workflow]
    Postgres[(PostgreSQL + pgvector)]
    Redis[(Redis Broker & Cache)]
    LLMProvider[LLM Provider: OpenAI / Gemini / Fallback]

    User <--> Gateway
    Gateway -->|/| SPA
    Gateway -->|/api/v1| API
    API --> AuthService
    API --> RepoService
    API --> RAGEngine
    RepoService --> IngestPipeline
    IngestPipeline --> Worker
    Worker --> Postgres
    Worker --> Redis
    RAGEngine --> Postgres
    RAGEngine --> LLMProvider
```

---

## 2. Core Subsystems

### 2.1 Repository Ingestion & Parsing Engine
The ingestion pipeline converts raw source trees into structured code chunks:
1. **Acquisition & Security**: Repositories are acquired via HTTPS Git cloning (`--depth=1`) or safe ZIP upload.
   - **Anti-SSRF**: URLs are validated to prevent targeting private IPs, AWS/GCP cloud metadata endpoints (`169.254.169.254`), or loopback interfaces.
   - **Zip Slip & Bomb Protection**: ZIP files are extracted ensuring no path leaves the workspace (`commonpath` checks) and decompressing stops if size exceeds 100MB or 1,000 files.
2. **File Filtering**: Excludes `.git`, `node_modules`, `dist`, `__pycache__`, binaries, lock files, and sensitive credentials (`.env`, `*.pem`, `*.key`).
3. **AST & Symbol Extraction**: Uses Python AST and language parsers to identify classes, methods, top-level functions, and line ranges.
4. **Code-Aware Chunking**: Chunks retain the enclosing symbol context and line boundaries rather than cutting blindly across fixed byte lengths.

---

### 2.2 Hybrid Retrieval Pipeline
```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant API as FastAPI Router
    participant Ret as HybridRetriever
    participant PG as PostgreSQL (pgvector + FTS)
    participant LLM as LLM Provider
    participant Val as Citation Validator

    Dev->>API: POST /api/v1/chat (Question)
    API->>Ret: search(query, mode="hybrid", top_k=8)
    par Dense Vector Search
        Ret->>PG: Cosine similarity on embeddings
    and Full-Text Keyword Search
        Ret->>PG: Keyword match with symbol bonus
    end
    Ret->>Ret: Reciprocal Rank Fusion (RRF)
    Ret-->>API: Top ranked CodeChunks
    API->>LLM: Generate structured response with context
    LLM-->>API: GroundedAnswerPayload
    API->>Val: Check cited file paths & line numbers
    Val-->>API: Verified citations
    API-->>Dev: Grounded Answer + Source Pills
```

---

## 3. Architectural Decisions & Trade-Offs

| Decision | Alternative Considered | Rationale & Trade-Off |
| :--- | :--- | :--- |
| **PostgreSQL + pgvector** | Pinecone / Qdrant / Milvus | Minimizes infrastructure complexity by unifying relational entities (users, repos, chat sessions) and dense embeddings in one ACID-compliant database. |
| **Code-Aware Chunks** | Fixed-size sliding text window | Fixed-size splits cut functions in half, destroying logic context. Hierarchical symbol chunking ensures each function/class retains its signature. |
| **Reciprocal Rank Fusion** | Pure vector similarity | Vector search often misses exact variable names or method identifiers. Combining full-text matching with dense embeddings guarantees both conceptual and literal recall. |
| **Monaco Editor in Frontend** | Simple `highlight.js` / `prism` | Monaco provides full VS Code syntax highlighting, line numbers, search within file, and programmatic line jumping when citations are clicked. |
