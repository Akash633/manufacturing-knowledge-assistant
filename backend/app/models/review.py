from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class ReviewItem(Base):
    __tablename__ = "review_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    item_type = Column(String(64), index=True, nullable=False)
    # Types: safety_critical_query, document_conflict, draft_work_instruction
    
    status = Column(String(32), index=True, default="pending")
    # Statuses: pending, approved, rejected, escalated, resolved
    
    priority = Column(String(16), default="medium")
    # Priorities: low, medium, high, critical
    
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    details_json = Column(Text, default="{}")
    proposed_action = Column(Text, nullable=True)
    
    expert_notes = Column(Text, nullable=True)
    reviewer = Column(String(64), nullable=True)
    
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
