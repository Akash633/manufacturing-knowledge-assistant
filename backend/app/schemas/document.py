from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ApprovalStatusEnum(str, Enum):
    APPROVED = "Approved"
    DRAFT = "Draft"
    PENDING_REVIEW = "Pending Review"
    SUPERSEDED = "Superseded"
    WITHDRAWN = "Withdrawn"
    EXPIRED = "Expired"
    NOT_YET_EFFECTIVE = "Not Yet Effective"

class DocumentBase(BaseModel):
    document_number: str
    title: str
    revision: str
    approval_status: ApprovalStatusEnum = ApprovalStatusEnum.DRAFT
    machine_model: str = "DEMO-CNC-01"
    section_category: str = "Standard Operating Procedure"
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    superseded_by_id: Optional[str] = None
    supersedes_id: Optional[str] = None
    is_synthetic_demo: bool = True

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    revision: Optional[str] = None
    approval_status: Optional[ApprovalStatusEnum] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    superseded_by_id: Optional[str] = None
    supersedes_id: Optional[str] = None

class DocumentResponse(DocumentBase):
    id: str
    file_path: str
    file_type: str
    file_size_bytes: int
    checksum: Optional[str] = None
    page_count: int
    metadata_json: str
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
