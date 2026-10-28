from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime

class DocumentConflict(BaseModel):
    conflict_id: str
    parameter_or_topic: str
    description: str
    document_a_id: str
    document_a_number: str
    document_a_revision: str
    document_a_status: str
    instruction_a: str
    document_b_id: str
    document_b_number: str
    document_b_revision: str
    document_b_status: str
    instruction_b: str
    severity: str # "high", "critical", "medium"
    recommended_action: str
    status: str = "detected" # "detected", "resolved", "flagged_for_review"
    winning_document_id: Optional[str] = None
    resolution_action: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

class RevisionCheckResult(BaseModel):
    is_authoritative: bool
    status: str
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    superseded_by: Optional[str] = None
    reason: str

class ConflictResolutionRequest(BaseModel):
    conflict_id: str
    resolution_notes: str = Field(..., min_length=3, max_length=4000)
    winning_document_id: str
    action_taken: Literal["mark_superseded", "withdraw_conflicting", "approve_exception"]
