import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import init_db, SessionLocal
from app.core.exceptions import RepoSageException
from app.api.v1.router import api_router
from app.api.v1.health import router as health_router
from app.models.user import User
from app.core.security import hash_password

logger = logging.getLogger(__name__)


def seed_dev_user():
    """Ensure a default user exists for development/interview demonstrations."""
    db = SessionLocal()
    try:
        demo = db.query(User).filter(User.email == "demo@reposage.dev").first()
        if not demo:
            demo_user = User(
                email="demo@reposage.dev",
                password_hash=hash_password("RepoSage123!"),
                is_active=True
            )
            db.add(demo_user)
            db.commit()
            logger.info("Demo user seeded: demo@reposage.dev / RepoSage123!")
    except Exception as e:
        logger.warning(f"Could not seed demo user: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    init_db()
    seed_dev_user()
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Understand, Debug, and Navigate Any Codebase with AI.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(RepoSageException)
async def domain_exception_handler(request: Request, exc: RepoSageException):
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "UNAUTHORIZED":
        status_code = status.HTTP_401_UNAUTHORIZED
    elif exc.code == "FORBIDDEN":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code == "SECURITY_VIOLATION":
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": exc.message,
            "error": exc.code,
            "data": None
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal server error occurred.",
            "error": "INTERNAL_SERVER_ERROR",
            "data": None
        }
    )


# Top-level routes
app.include_router(health_router)
app.include_router(api_router)

# Direct root-level bindings for exact specification compliance
from app.api.v1.repositories import router as repos_router
from app.api.v1.debug import router as debug_root_router
from app.api.v1.runs import router as runs_root_router
from app.api.v1.patches import router as patches_root_router

app.include_router(repos_router)
app.include_router(debug_root_router)
app.include_router(runs_root_router)
app.include_router(patches_root_router)
