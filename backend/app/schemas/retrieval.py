from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class RetrievalModeEnum(str, Enum):
    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"

class RetrievalQuery(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    mode: RetrievalModeEnum = RetrievalModeEnum.HYBRID
    top_k: int = Field(default=5, ge=1, le=20)
    filter_approved_only: bool = True
    machine_model: Optional[str] = None
    target_document_id: Optional[str] = None

class RetrievedPassage(BaseModel):
    chunk_id: str
    document_id: str
    document_number: str
    document_title: str
    revision: str
    approval_status: str
    is_authoritative: bool
    page_number: int
    section_title: str
    content: str
    score: float # Final score (BM25, vector similarity, or RRF combined)
    bm25_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None
    has_images: bool = False
    image_paths: List[str] = []
    ocr_applied: bool = False

class RetrievalResponse(BaseModel):
    query: str
    retrieval_mode: str
    total_chunks_searched: int
    retrieval_latency_ms: float
    results: List[RetrievedPassage]
    provider_used: str
    fallback_triggered: bool = False
