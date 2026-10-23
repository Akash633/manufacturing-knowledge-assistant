from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import Document
from app.models.audit import AuditLog
from app.schemas.governance import DocumentConflict, ConflictResolutionRequest
from app.governance.conflict_detector import conflict_detector
from app.governance.revision_rules import revision_governance
from app.services.audit_service import audit_service

router = APIRouter(prefix="/governance", tags=["Revision Governance"])

@router.get("/conflicts", response_model=List[DocumentConflict])
def get_document_conflicts(db: Session = Depends(get_db)):
    """
    Scans active approved documents and quality alerts to detect
    conflicting operating limits or contradictory technical parameters.
    """
    return conflict_detector.scan_for_conflicts(db)

@router.post("/conflicts/resolve")
def resolve_document_conflict(
    req: ConflictResolutionRequest,
    db: Session = Depends(get_db),
):
    """
    Records an authorized human resolution for a detected technical conflict.
    """
    if req.winning_document_id and req.action_taken == "mark_superseded":
        # Supersede the other document
        pass

    audit_service.log_action(
        db=db,
        action="CONFLICT_RESOLVED",
        actor=req.resolver,
        resource_type="document_conflict",
        resource_id=req.conflict_id,
        details={
            "action_taken": req.action_taken,
            "winning_document_id": req.winning_document_id,
            "resolution_notes": req.resolution_notes,
        },
    )
    return {
        "status": "resolved",
        "conflict_id": req.conflict_id,
        "message": f"Conflict {req.conflict_id} resolved by {req.resolver}."
    }

@router.get("/revision-matrix")
def get_revision_matrix(db: Session = Depends(get_db)):
    """
    Returns document revision family trees with explicit authority evaluations.
    """
    docs = db.query(Document).order_by(Document.document_number.asc(), Document.revision.desc()).all()
    matrix = []

    for d in docs:
        auth = revision_governance.evaluate_authority(d)
        matrix.append({
            "id": d.id,
            "document_number": d.document_number,
            "title": d.title,
            "revision": d.revision,
            "approval_status": d.approval_status,
            "machine_model": d.machine_model,
            "section_category": d.section_category,
            "effective_date": d.effective_date,
            "expiry_date": d.expiry_date,
            "superseded_by_id": d.superseded_by_id,
            "supersedes_id": d.supersedes_id,
            "is_authoritative": auth.is_authoritative,
            "authority_reason": auth.reason,
            "page_count": d.page_count,
            "chunk_count": len(d.chunks),
            "updated_at": d.updated_at,
        })

    return matrix

@router.get("/audit-trail")
def get_audit_trail(limit: int = 50, db: Session = Depends(get_db)):
    """
    Retrieves recent audit log events for traceability.
    """
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return logs
