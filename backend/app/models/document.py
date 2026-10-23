from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_number = Column(String(64), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    revision = Column(String(32), nullable=False)
    approval_status = Column(String(32), index=True, nullable=False, default="Draft")
    # Statuses: Approved, Draft, Pending Review, Superseded, Withdrawn, Expired, Not Yet Effective
    
    machine_model = Column(String(64), index=True, default="DEMO-CNC-01")
    section_category = Column(String(64), default="Standard Operating Procedure")
    
    effective_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    
    superseded_by_id = Column(String(36), nullable=True)
    supersedes_id = Column(String(36), nullable=True)
    
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(16), nullable=False) # "pdf", "docx"
    file_size_bytes = Column(Integer, default=0)
    checksum = Column(String(64), nullable=True) # sha256
    page_count = Column(Integer, default=1)
    
    metadata_json = Column(Text, default="{}")
    is_synthetic_demo = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
