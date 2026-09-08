import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application Settings
    APP_NAME: str = "RepoSage"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-this-to-a-very-secure-random-secret-key-in-production"
    DEBUG: bool = True

    # Database & Cache
    DATABASE_URL: str = "sqlite:///./reposage.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Vector Storage (Qdrant)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "reposage_code_chunks"
    QDRANT_USE_MEMORY: bool = False

    # Security & JWT Auth
    JWT_SECRET_KEY: str = "change-this-jwt-secret-key-to-a-secure-random-string-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Providers Configuration
    LLM_PROVIDER: str = "openai"  # openai, gemini, mock
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key")
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_TOKENS: int = 2500

    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    GEMINI_MODEL: str = "gemini-3.8-flash"

    # Embedding Settings
    EMBEDDING_PROVIDER: str = "openai"  # openai, sentence-transformers, mock
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_BATCH_SIZE: int = 64

    # Repository Ingestion Constraints & Security Limits
    MAX_REPOSITORY_SIZE_MB: int = 100
    MAX_FILE_SIZE_MB: int = 5
    MAX_ARCHIVE_FILES: int = 1000
    MAX_CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 150
    REPO_STORAGE_PATH: str = "./data/repositories"

    # Retrieval & Search Settings
    TOP_K_RETRIEVAL: int = 10
    SIMILARITY_THRESHOLD: float = 0.3
    RERANKING_ENABLED: bool = False
    HYBRID_SEARCH_ALPHA: float = 0.65

    # CORS and Network Security
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    FRONTEND_URL: str = "http://localhost:5173"

    # Sandbox & Execution Safety
    SANDBOX_EXECUTION_ENABLED: bool = False
    SANDBOX_TIMEOUT_SECONDS: int = 15

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
