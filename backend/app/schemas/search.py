from typing import List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    repository_id: str
    query: str = Field(min_length=1, description="Natural language or keyword search query")
    search_type: str = Field(default="hybrid", description="dense, keyword, hybrid, symbol")
    file_filter: Optional[str] = Field(default=None, description="Optional path prefix filter")
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResultItem(BaseModel):
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str]
    symbol_type: Optional[str]
    language: Optional[str]
    content: str
    score: float
    retrieval_method: str  # dense, keyword, symbol, hybrid


class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: List[SearchResultItem]
