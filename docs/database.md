# RepoSage Database Design & Schema

RepoSage utilizes PostgreSQL 16 with the `pgvector` extension for dense embedding storage, supplemented with full-text search indexing and relational constraints.

```mermaid
erDiagram
    USERS ||--o{ REPOSITORIES : owns
    USERS ||--o{ CHAT_SESSIONS : participates
    USERS ||--o{ CODE_CHANGES : approves
    REPOSITORIES ||--o{ REPOSITORY_FILES : contains
    REPOSITORIES ||--o{ CODE_CHUNKS : indexes
    REPOSITORIES ||--o{ INGESTION_JOBS : triggers
    REPOSITORIES ||--o{ CHAT_SESSIONS : has
    REPOSITORY_FILES ||--o{ CODE_CHUNKS : contains
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : records

    USERS {
        string id PK
        string email UK
        string password_hash
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    REPOSITORIES {
        string id PK
        string user_id FK
        string name
        string source_type
        string source_url
        string default_branch
        string commit_sha
        string primary_language
        string status
        int total_files
        int total_chunks
        string local_path
        datetime created_at
        datetime last_indexed_at
    }

    REPOSITORY_FILES {
        string id PK
        string repository_id FK
        string file_path
        string language
        string content_hash
        int file_size
        datetime indexed_at
    }

    CODE_CHUNKS {
        string id PK
        string repository_id FK
        string file_id FK
        text content
        string symbol_name
        string symbol_type
        int start_line
        int end_line
        string language
        text embedding_json
        text metadata_json
        datetime created_at
    }

    CHAT_SESSIONS {
        string id PK
        string user_id FK
        string repository_id FK
        string title
        datetime created_at
        datetime updated_at
    }

    CHAT_MESSAGES {
        string id PK
        string session_id FK
        string role
        text content
        text citations_json
        string model
        text token_usage_json
        datetime created_at
    }

    INGESTION_JOBS {
        string id PK
        string repository_id FK
        string status
        int progress
        string current_stage
        text error_message
        datetime started_at
        datetime completed_at
    }

    CODE_CHANGES {
        string id PK
        string repository_id FK
        string user_id FK
        string original_commit_sha
        text patch_content
        string status
        datetime created_at
        datetime approved_at
        datetime applied_at
    }
```

---

## Indexing & Performance Optimizations
1. **Foreign Key Cascades**: Deleting a repository cascades cleanly down to `repository_files`, `code_chunks`, `chat_sessions`, and `ingestion_jobs`.
2. **Dense Vector Indexes**: In production PostgreSQL, `code_chunks` uses an IVFFlat or HNSW cosine similarity index:
   ```sql
   CREATE INDEX ON code_chunks USING hnsw (embedding vector_cosine_ops);
   ```
3. **Compound Lookups**: Indexes on `(repository_id, file_path)` and `(repository_id, symbol_name)` guarantee sub-millisecond symbol resolution.
