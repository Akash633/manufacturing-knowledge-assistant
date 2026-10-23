import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.api.routes import api_router
from app.models import Document, DocumentChunk, AuditLog, ReviewItem, DraftWorkInstruction

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Revision-Aware Multimodal AI Assistant for Traceable Shop Floor Operations",
    debug=settings.DEBUG,
)

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

@app.on_event("startup")
def on_startup():
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized.")

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
def health_check():
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "environment": settings.ENVIRONMENT,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "llm_provider": settings.LLM_PROVIDER,
    }
