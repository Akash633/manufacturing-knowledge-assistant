from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action = Column(String(64), index=True, nullable=False)
    # Actions: DOCUMENT_UPLOAD, STATUS_CHANGE, QUERY_ANSWERED, QUERY_ABSTAINED, CONFLICT_DETECTED, CONFLICT_RESOLVED, REVIEW_SUBMITTED, REVIEW_DECISION, INSTRUCTION_DRAFTED, INSTRUCTION_APPROVED
    actor = Column(String(64), default="system")
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    details_json = Column(Text, default="{}")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
