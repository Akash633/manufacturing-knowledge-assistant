from sqlalchemy import Column, String, DateTime, Text, Boolean
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class DraftWorkInstruction(Base):
    __tablename__ = "draft_work_instructions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    instruction_number = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    machine_model = Column(String(64), default="DEMO-CNC-01")
    task_summary = Column(Text, nullable=False)
    
    # Traceability: must reference approved documents only!
    approved_source_doc_ids_json = Column(Text, nullable=False, default="[]")
    
    steps_json = Column(Text, nullable=False, default="[]")
    safety_warnings_json = Column(Text, nullable=False, default="[]")
    required_ppe_json = Column(Text, nullable=False, default="[]")
    
    status = Column(String(32), index=True, default="draft")
    # Statuses: draft, pending_review, approved, rejected
    
    # Must remain unpublished until authorized reviewer approves!
    is_published = Column(Boolean, default=False)
    
    created_by = Column(String(64), default="assistant_generator")
    reviewed_by = Column(String(64), nullable=True)
    review_comments = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
