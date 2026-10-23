from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from .retrieval import RetrievedPassage, RetrievalModeEnum

class AbstentionReasonEnum(str, Enum):
    NONE = "none"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    DOCUMENT_CONFLICT = "document_conflict"
    SUPERSEDED_ONLY = "superseded_only"
    SAFETY_ESCALATION = "safety_escalation"
    OUT_OF_SCOPE = "out_of_scope"

class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    retrieval_mode: RetrievalModeEnum = RetrievalModeEnum.HYBRID
    machine_model: Optional[str] = "DEMO-CNC-01"
    top_k: int = Field(default=5, ge=1, le=10)
    filter_approved_only: bool = True
    allow_expert_bypass: bool = False # Configured so model confidence cannot bypass review

class Citation(BaseModel):
    citation_id: str
    chunk_id: str
    document_id: str
    document_number: str
    revision: str
    approval_status: str
    page_number: int
    section_title: str
    snippet: str
    is_authoritative: bool
    is_valid: bool = True # Validated strictly against retrieved chunks!

class SafetyEscalationInfo(BaseModel):
    is_safety_critical: bool
    risk_level: str # "none", "low", "medium", "high", "critical"
    matched_rules: List[str] = []
    escalation_reason: Optional[str] = None
    requires_expert_review: bool = False
    review_item_id: Optional[str] = None

class GroundedAnswerResponse(BaseModel):
    question: str
    answer: str
    abstained: bool
    abstention_reason: AbstentionReasonEnum
    abstention_explanation: Optional[str] = None
    citations: List[Citation]
    retrieved_passages: List[RetrievedPassage]
    safety_escalation: SafetyEscalationInfo
    conflicts_detected: List[str] = []
    authoritative_doc_ids: List[str] = []
    retrieval_mode_used: str
    provider_used: str
    latency_ms: float
    audit_log_id: Optional[str] = None
