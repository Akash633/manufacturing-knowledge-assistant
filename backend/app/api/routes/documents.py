import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.schemas.document import DocumentResponse, DocumentListResponse, ApprovalStatusEnum
from app.ingestion.parser import document_parser
from app.retrieval.vector import embedding_provider
from app.services.audit_service import audit_service
from app.governance.revision_rules import revision_governance

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_number: str = Form(...),
    title: str = Form(...),
    revision: str = Form(...),
    approval_status: str = Form("Draft"),
    machine_model: str = Form("DEMO-CNC-01"),
    section_category: str = Form("Standard Operating Procedure"),
    effective_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    supersedes_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Only .pdf and .docx files are permitted."
        )

    doc_id = str(uuid.uuid4())
    stored_filename = f"{doc_id}_{file.filename}"
    saved_path = settings.UPLOAD_DIR / stored_filename

    # Save to disk
    try:
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Failed to save upload {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

    # Ingestion & Parsing
    try:
        parsed_data = document_parser.parse_document(saved_path, doc_id)
    except Exception as e:
        logger.error(f"Parsing error for {file.filename}: {e}")
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=422, detail=f"Document parsing failed: {str(e)}")

    eff_dt = datetime.fromisoformat(effective_date) if effective_date else None
    exp_dt = datetime.fromisoformat(expiry_date) if expiry_date else None

    # Create Document record
    doc = Document(
        id=doc_id,
        document_number=document_number.strip().upper(),
        title=title.strip(),
        revision=revision.strip(),
        approval_status=approval_status,
        machine_model=machine_model.strip(),
        section_category=section_category.strip(),
        effective_date=eff_dt,
        expiry_date=exp_dt,
        supersedes_id=supersedes_id,
        file_path=str(saved_path),
        file_type=parsed_data["file_type"],
        file_size_bytes=parsed_data["file_size_bytes"],
        checksum=parsed_data["checksum"],
        page_count=parsed_data["page_count"],
        metadata_json=json.dumps({"original_filename": file.filename}),
        is_synthetic_demo=True,
    )
    db.add(doc)
    db.commit()

    # Create Chunks with Dense Embeddings
    raw_chunks = parsed_data["chunks"]
    contents_for_embedding = [c["content"] for c in raw_chunks]
    embeddings = embedding_provider.embed_batch(contents_for_embedding) if contents_for_embedding else []

    db_chunks = []
    for idx, c in enumerate(raw_chunks):
        emb_json = json.dumps(embeddings[idx]) if idx < len(embeddings) else None
        db_chunk = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            chunk_index=c["chunk_index"],
            page_number=c["page_number"],
            section_title=c["section_title"],
            content=c["content"],
            token_count=c["token_count"],
            has_images=c["has_images"],
            image_paths_json=c["image_paths_json"],
            ocr_applied=c["ocr_applied"],
            embedding_vector_json=emb_json,
        )
        db_chunks.append(db_chunk)

    db.bulk_save_objects(db_chunks)
    db.commit()
    db.refresh(doc)

    # If this document supersedes an older one, update the older document's superseded_by_id and status
    if supersedes_id:
        old_doc = db.query(Document).filter(Document.id == supersedes_id).first()
        if old_doc:
            old_doc.superseded_by_id = doc.id
            old_doc.approval_status = "Superseded"
            db.commit()

    # Audit Trail
    audit_service.log_action(
        db=db,
        action="DOCUMENT_UPLOAD",
        actor="quality_engineer",
        resource_type="document",
        resource_id=doc.id,
        details={
            "document_number": doc.document_number,
            "revision": doc.revision,
            "status": doc.approval_status,
            "chunks_count": len(db_chunks),
            "page_count": doc.page_count,
        },
    )

    resp = DocumentResponse.model_validate(doc)
    resp.chunk_count = len(db_chunks)
    return resp

@router.get("", response_model=DocumentListResponse)
def list_documents(
    approval_status: Optional[str] = Query(None),
    machine_model: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if approval_status:
        q = q.filter(Document.approval_status == approval_status)
    if machine_model:
        q = q.filter(Document.machine_model == machine_model)

    total = q.count()
    items = q.order_by(Document.document_number.asc(), Document.revision.desc()).offset(skip).limit(limit).all()

    result = []
    for d in items:
        resp = DocumentResponse.model_validate(d)
        resp.chunk_count = len(d.chunks)
        result.append(resp)

    return DocumentListResponse(items=result, total=total)

@router.get("/{doc_id}")
def get_document_details(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index.asc()).all()
    authority_eval = revision_governance.evaluate_authority(doc)

    return {
        "document": DocumentResponse.model_validate(doc),
        "authority_evaluation": authority_eval.model_dump(),
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "section_title": c.section_title,
                "content": c.content,
                "token_count": c.token_count,
                "has_images": c.has_images,
                "image_paths": json.loads(c.image_paths_json) if c.image_paths_json else [],
                "ocr_applied": c.ocr_applied,
            }
            for c in chunks
        ],
    }

@router.patch("/{doc_id}/status", response_model=DocumentResponse)
def update_document_status(
    doc_id: str,
    approval_status: str = Body(..., embed=True),
    superseded_by_id: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
):
    from fastapi import Body
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    old_status = doc.approval_status
    doc.approval_status = approval_status
    if superseded_by_id:
        doc.superseded_by_id = superseded_by_id
    db.commit()
    db.refresh(doc)

    audit_service.log_action(
        db=db,
        action="STATUS_CHANGE",
        actor="plant_supervisor",
        resource_type="document",
        resource_id=doc.id,
        details={"old_status": old_status, "new_status": approval_status},
    )

    resp = DocumentResponse.model_validate(doc)
    resp.chunk_count = len(doc.chunks)
    return resp

@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass

    db.delete(doc)
    db.commit()

    audit_service.log_action(
        db=db,
        action="DOCUMENT_DELETE",
        actor="administrator",
        resource_type="document",
        resource_id=doc_id,
        details={"document_number": doc.document_number},
    )
    return {"status": "success", "message": f"Document {doc.document_number} deleted"}

@router.get("/images/{filename}")
def serve_extracted_image(filename: str):
    file_path = settings.IMAGE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)
