from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class InstructionStep(BaseModel):
    step_number: int
    title: str
    description: str
    safety_hazard: Optional[str] = None
    verification_check: Optional[str] = None
    source_citation: Optional[str] = None

class WorkInstructionCreateRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    task_summary: str = Field(..., min_length=10)
    machine_model: str = "DEMO-CNC-01"
    target_operation: str # e.g. "Spindle warm-up & Chuck inspection"
    require_approved_sources_only: bool = True

class WorkInstructionResponse(BaseModel):
    id: str
    instruction_number: str
    title: str
    machine_model: str
    task_summary: str
    approved_source_doc_ids: List[str]
    steps: List[InstructionStep]
    safety_warnings: List[str]
    required_ppe: List[str]
    status: str
    is_published: bool # Must remain unpublished until authorized reviewer approves!
    created_by: str
    reviewed_by: Optional[str] = None
    review_comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
