from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ReviewItemResponse(BaseModel):
    id: str
    item_type: str
    status: str
    priority: str
    title: str
    summary: str
    details: Dict[str, Any] = {}
    proposed_action: Optional[str] = None
    expert_notes: Optional[str] = None
    reviewer: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class ReviewActionRequest(BaseModel):
    action: str = Field(..., description="'approve', 'reject', 'escalate', or 'resolve'")
    expert_notes: str = Field(..., min_length=3)
    reviewer_name: str = Field(default="Senior Manufacturing Specialist")
