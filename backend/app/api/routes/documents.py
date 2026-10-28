import os
import re
import zipfile
import uuid
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.auth import AuthenticatedUser, get_optional_user, require_optional_user_role, require_roles
from app.db.session import get_db
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.schemas.document import DocumentResponse, DocumentListResponse, ApprovalStatusEnum
from app.ingestion.parser import document_parser
from app.retrieval.vector import embedding_provider
from app.services.audit_service import audit_service
from app.governance.revision_rules import revision_governance

router = APIRouter(prefix="/documents", tags=["Documents"])


def _cleanup_upload(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.error(f"Failed to remove temporary upload {path.name}: {type(exc).__name__}")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_number: str = Form(...),
    title: str = Form(...),
    revision: str = Form(...),
    approval_status: str = Form("Draft"),
    machine_model: str = Form("DEMO-CNC-01"),
    section_category: str = Form("Standard Operating Procedure"),
    effective_date: Optional[datetime] = Form(None),
    expiry_date: Optional[datetime] = Form(None),
    supersedes_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
):
    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Only .pdf and .docx files are permitted."
        )

    user = require_optional_user_role(user, "document_uploader")
    if approval_status != "Draft" or supersedes_id:
        user = require_optional_user_role(user, "document_approver")

    try:
        status = ApprovalStatusEnum(approval_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unsupported document approval status.")
    if supersedes_id and status != ApprovalStatusEnum.APPROVED:
        raise HTTPException(status_code=400, detail="A superseding document must be uploaded as Approved.")

    old_doc = None
    if supersedes_id:
        old_doc = db.query(Document).filter(Document.id == supersedes_id).first()
        if old_doc is None:
            raise HTTPException(status_code=404, detail="The document to supersede was not found.")
        if not revision_governance.evaluate_authority(old_doc).is_authoritative:
            raise HTTPException(status_code=409, detail="Only an authoritative revision can be superseded.")
        if (
            old_doc.document_number != document_number.strip().upper()
            or old_doc.machine_model != machine_model.strip()
        ):
            raise HTTPException(
                status_code=400,
                detail="A superseding document must belong to the same document and machine family.",
            )

    doc_id = str(uuid.uuid4())
    original_filename = Path((file.filename or "upload").replace("\\", "/")).name
    original_filename = re.sub(r"[\x00-\x1f\x7f]", "", original_filename)[:255] or "upload"
    stored_filename = f"{doc_id}_{original_filename}"
    saved_path = settings.UPLOAD_DIR / stored_filename
    temporary_path = settings.UPLOAD_DIR / f".{doc_id}.uploading{ext}"

    max_upload_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    uploaded_bytes = 0
    try:
        with open(temporary_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                if uploaded_bytes + len(chunk) > max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploaded file exceeds the {settings.MAX_FILE_SIZE_MB} MB limit.",
                    )
                f.write(chunk)
                uploaded_bytes += len(chunk)
    except HTTPException:
        _cleanup_upload(temporary_path)
        raise
    except Exception as e:
        _cleanup_upload(temporary_path)
        logger.error(f"Failed to save upload {original_filename}: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from e

    try:
        with open(temporary_path, "rb") as file_handle:
            signature = file_handle.read(8)
        if ext == ".pdf" and not signature.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")
        if ext == ".docx":
            if not signature.startswith(b"PK"):
                raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX.")
            with zipfile.ZipFile(temporary_path) as archive:
                members = archive.infolist()
                if (
                    len(members) > 1000
                    or sum(member.file_size for member in members) > 100 * 1024 * 1024
                    or "[Content_Types].xml" not in archive.namelist()
                    or "word/document.xml" not in archive.namelist()
                ):
                    raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX.")
    except HTTPException:
        _cleanup_upload(temporary_path)
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        _cleanup_upload(temporary_path)
        logger.warning(f"Upload validation or parsing failed for {original_filename}: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF or DOCX.") from e

    try:
        parsed_data = document_parser.parse_document(temporary_path, doc_id)
    except Exception as e:
        _cleanup_upload(temporary_path)
        logger.warning(f"Document parsing failed for {original_filename}: {type(e).__name__}")
        raise HTTPException(
            status_code=422,
            detail="The uploaded document could not be parsed as a valid PDF or DOCX.",
        ) from e

    raw_chunks = parsed_data["chunks"]
    try:
        contents_for_embedding = [chunk["content"] for chunk in raw_chunks]
        embeddings = (
            embedding_provider.embed_batch(contents_for_embedding)
            if contents_for_embedding
            else []
        )

        doc = Document(
            id=doc_id,
            document_number=document_number.strip().upper(),
            title=title.strip(),
            revision=revision.strip(),
            approval_status=status.value,
            machine_model=machine_model.strip(),
            section_category=section_category.strip(),
            effective_date=effective_date,
            expiry_date=expiry_date,
            supersedes_id=supersedes_id,
            file_path=str(saved_path),
            file_type=parsed_data["file_type"],
            file_size_bytes=parsed_data["file_size_bytes"],
            checksum=parsed_data["checksum"],
            page_count=parsed_data["page_count"],
            metadata_json=json.dumps({"original_filename": original_filename}),
            is_synthetic_demo=settings.DEMO_MODE,
        )
        db.add(doc)
        db.flush()

        db_chunks = []
        for index, chunk in enumerate(raw_chunks):
            emb_json = json.dumps(embeddings[index]) if index < len(embeddings) else None
            db_chunks.append(
                DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    chunk_index=chunk["chunk_index"],
                    page_number=chunk["page_number"],
                    section_title=chunk["section_title"],
                    content=chunk["content"],
                    token_count=chunk["token_count"],
                    has_images=chunk["has_images"],
                    image_paths_json=chunk["image_paths_json"],
                    ocr_applied=chunk["ocr_applied"],
                    embedding_vector_json=emb_json,
                )
            )
        db.bulk_save_objects(db_chunks)
        if old_doc:
            old_doc.superseded_by_id = doc.id
            old_doc.approval_status = "Superseded"
        temporary_path.replace(saved_path)
        db.commit()
        db.refresh(doc)
    except Exception as e:
        db.rollback()
        _cleanup_upload(temporary_path)
        _cleanup_upload(saved_path)
        logger.error(f"Failed to persist upload {original_filename}: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="The uploaded document could not be saved.") from e

    # Audit Trail
    audit_service.log_action(
        db=db,
        action="DOCUMENT_UPLOAD",
        actor=user.subject if user else "anonymous",
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
    search: Optional[str] = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if approval_status:
        q = q.filter(Document.approval_status == approval_status)
    if machine_model:
        q = q.filter(Document.machine_model == machine_model)
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        q = q.filter(
            (Document.document_number.ilike(search_term))
            | (Document.title.ilike(search_term))
        )

    total = q.count()
    items = q.order_by(Document.document_number.asc(), Document.revision.desc()).offset(skip).limit(limit).all()

    result = []
    for d in items:
        resp = DocumentResponse.model_validate(d)
        resp.chunk_count = len(d.chunks)
        result.append(resp)

    return DocumentListResponse(items=result, total=total)

@router.get("/summary")
def get_document_summary(db: Session = Depends(get_db)):
    status_counts = (
        db.query(Document.approval_status, func.count(Document.id))
        .group_by(Document.approval_status)
        .all()
    )
    return {
        "total_documents": sum(count for _, count in status_counts),
        "synthetic_documents": db.query(Document).filter(Document.is_synthetic_demo.is_(True)).count(),
        "status_counts": {status: count for status, count in status_counts},
    }

@router.get("/machines")
def list_machine_models(db: Session = Depends(get_db)):
    models = (
        db.query(Document.machine_model)
        .filter(Document.machine_model.isnot(None))
        .distinct()
        .order_by(Document.machine_model.asc())
        .all()
    )
    return {"items": [model for (model,) in models]}

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
    user: AuthenticatedUser = Depends(require_roles("document_approver")),
):
    from fastapi import Body
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    old_status = doc.approval_status
    try:
        status = ApprovalStatusEnum(approval_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unsupported document approval status.")
    if status == ApprovalStatusEnum.SUPERSEDED:
        if not superseded_by_id:
            raise HTTPException(status_code=400, detail="Choose the document that supersedes this revision.")
        replacement = db.query(Document).filter(Document.id == superseded_by_id).first()
        if (
            replacement is None
            or replacement.id == doc.id
            or replacement.document_number != doc.document_number
            or replacement.machine_model != doc.machine_model
        ):
            raise HTTPException(status_code=400, detail="The superseding document is not in this document family.")
        doc.superseded_by_id = replacement.id
    else:
        doc.superseded_by_id = None
    doc.approval_status = status.value
    db.commit()
    db.refresh(doc)

    audit_service.log_action(
        db=db,
        action="STATUS_CHANGE",
        actor=user.subject,
        resource_type="document",
        resource_id=doc.id,
        details={"old_status": old_status, "new_status": approval_status},
    )

    resp = DocumentResponse.model_validate(doc)
    resp.chunk_count = len(doc.chunks)
    return resp

@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError as exc:
            logger.error(f"Failed to remove document file {file_path.name}: {type(exc).__name__}")
            raise HTTPException(status_code=500, detail="The document file could not be removed.") from exc

    db.delete(doc)
    db.commit()

    audit_service.log_action(
        db=db,
        action="DOCUMENT_DELETE",
        actor=user.subject,
        resource_type="document",
        resource_id=doc_id,
        details={"document_number": doc.document_number},
    )
    return {"status": "success", "message": f"Document {doc.document_number} deleted"}

@router.get("/images/{filename}")
def serve_extracted_image(filename: str):
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid image filename.")
    file_path = settings.IMAGE_DIR / filename
    if file_path.resolve().parent != settings.IMAGE_DIR.resolve() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)
