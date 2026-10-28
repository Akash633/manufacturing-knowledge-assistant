import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

# Project root directory
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "Revision-Aware Multimodal Manufacturing AI Assistant"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database & Storage
    DATA_DIR: Path = WORKSPACE_ROOT / "data"
    DATABASE_URL: str = f"sqlite:///{WORKSPACE_ROOT / 'data' / 'mfg_assistant.db'}"
    UPLOAD_DIR: Path = WORKSPACE_ROOT / "data" / "uploads"
    IMAGE_DIR: Path = WORKSPACE_ROOT / "data" / "extracted_images"
    SYNTHETIC_CORPUS_DIR: Path = WORKSPACE_ROOT / "data" / "synthetic_corpus"
    EVALUATION_DIR: Path = WORKSPACE_ROOT / "data" / "evaluation"

    # Retrieval
    DEFAULT_RETRIEVAL_MODE: str = "hybrid" # "bm25", "vector", "hybrid"
    TOP_K_RETRIEVAL: int = 5
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    RRF_K: int = 60
    EMBEDDING_PROVIDER: str = "fallback" # "fallback" (deterministic TF-IDF/n-gram hashing) or "sentence-transformers"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # LLM Settings
    LLM_PROVIDER: str = "deterministic_demo" # "deterministic_demo", "openai", "custom_endpoint"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    LOCAL_MODEL_ENDPOINT: Optional[str] = None

    # OIDC bearer-token verification for protected write operations
    OIDC_ISSUER: Optional[str] = None
    OIDC_AUDIENCE: Optional[str] = None
    OIDC_JWKS_URL: Optional[str] = None
    OIDC_ROLES_CLAIM: str = "roles"

    # Safety & Governance
    DEMO_MODE: bool = True
    STRICT_REVISION_FILTER: bool = True
    ALLOW_SUPERSEDED_FALLBACK: bool = False
    HIGH_RISK_MANDATORY_REVIEW: bool = True
    MAX_FILE_SIZE_MB: int = 25

    model_config = {
        "env_file": ".env",
        "extra": "allow"
    }

settings = Settings()

# Ensure directories exist
for directory in [
    settings.DATA_DIR,
    settings.UPLOAD_DIR,
    settings.IMAGE_DIR,
    settings.SYNTHETIC_CORPUS_DIR,
    settings.EVALUATION_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
