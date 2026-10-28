from contextlib import asynccontextmanager
import time
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth import oidc_is_configured
from app.core.logging import logger
from app.core.upload_limits import UploadBodyLimitMiddleware
from app.db.migrations import ensure_review_origin_column
from app.llm.provider import llm_provider
from app.db.base import Base
from app.db.session import engine, get_db
from app.api.routes import api_router
from app.models import (
    AuditLog,
    ConflictResolution,
    Document,
    DocumentChunk,
    DraftWorkInstruction,
    ReviewItem,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    ensure_review_origin_column(engine)
    logger.info("Database schema initialized.")
    yield

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Revision-Aware Multimodal AI Assistant for Traceable Shop Floor Operations",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(UploadBodyLimitMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "status": "operational",
        "version": "1.0.0",
        "docs_url": "/docs",
        "api_prefix": "/api",
    }

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error(f"Health check database probe failed: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc

    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "environment": settings.ENVIRONMENT,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "llm_provider": llm_provider.provider_name,
        "demo_mode": settings.DEMO_MODE,
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "authentication_configured": oidc_is_configured(),
    }
