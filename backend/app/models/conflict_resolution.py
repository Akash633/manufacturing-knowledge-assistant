from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base


class ConflictResolution(Base):
    __tablename__ = "conflict_resolutions"

    conflict_id = Column(String(64), primary_key=True)
    parameter_or_topic = Column(String(128), nullable=False)
    document_a_id = Column(String(36), nullable=False)
    document_b_id = Column(String(36), nullable=False)
    winning_document_id = Column(String(36), nullable=False)
    action_taken = Column(String(32), nullable=False)
    resolution_notes = Column(Text, nullable=False)
    resolver = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
