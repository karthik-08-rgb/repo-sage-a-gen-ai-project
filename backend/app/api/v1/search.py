from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.schemas.common import APIResponse
from app.services.retrieval.retriever import HybridRetriever

router = APIRouter(prefix="/search", tags=["Search & Code Retrieval"])


@router.post("", response_model=APIResponse[SearchResponse])
def search_codebase(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute dense semantic, keyword, symbol, or hybrid search across indexed chunks."""
    repo = db.query(Repository).filter(Repository.id == req.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    retriever = HybridRetriever(db, req.repository_id)
    results = retriever.search(
        query=req.query,
        search_type=req.search_type,
        top_k=req.top_k,
        file_filter=req.file_filter
    )

    items = [
        SearchResultItem(
            chunk_id=r.id,
            file_path=r.file_path,
            start_line=r.start_line,
            end_line=r.end_line,
            symbol_name=r.symbol_name,
            symbol_type=r.symbol_type,
            language=r.language,
            content=r.content,
            score=r.score,
            retrieval_method=r.retrieval_method
        )
        for r in results
    ]

    return APIResponse(
        success=True,
        message="Search completed",
        data=SearchResponse(
            query=req.query,
            search_type=req.search_type,
            total_results=len(items),
            results=items
        )
    )
