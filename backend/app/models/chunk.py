from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False, default=1) # 1-indexed
    section_title = Column(String(255), default="General")
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    
    # Multimodal indicators
    has_images = Column(Boolean, default=False)
    image_paths_json = Column(Text, default="[]") # JSON list of relative paths to extracted images
    ocr_applied = Column(Boolean, default=False)
    
    # Vector embedding storage (JSON array of floats)
    embedding_vector_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    document = relationship("Document", back_populates="chunks")
