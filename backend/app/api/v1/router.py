from fastapi import APIRouter
from app.api.v1 import (
    auth,
    repositories,
    chat,
    search,
    debug,
    review,
    code,
    jobs,
    health,
    runs,
    patches,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(repositories.router)
api_router.include_router(chat.router)
api_router.include_router(search.router)
api_router.include_router(debug.router)
api_router.include_router(review.router)
api_router.include_router(code.router)
api_router.include_router(jobs.router)
api_router.include_router(health.router)
api_router.include_router(runs.router)
api_router.include_router(patches.router)
