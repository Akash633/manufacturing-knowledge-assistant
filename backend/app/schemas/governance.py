from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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

class RevisionCheckResult(BaseModel):
    is_authoritative: bool
    status: str
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    superseded_by: Optional[str] = None
    reason: str

class ConflictResolutionRequest(BaseModel):
    conflict_id: str
    resolution_notes: str
    winning_document_id: Optional[str] = None
    action_taken: str # "mark_superseded", "withdraw_conflicting", "approve_exception"
    resolver: str = "quality_engineer"
