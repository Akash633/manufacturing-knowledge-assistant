from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_roles, require_user_role
from app.db.session import get_db
from app.models.document import Document
from app.models.audit import AuditLog
from app.models.conflict_resolution import ConflictResolution
from app.schemas.governance import DocumentConflict, ConflictResolutionRequest
from app.governance.conflict_detector import conflict_detector
from app.governance.revision_rules import revision_governance
from app.services.audit_service import audit_service

router = APIRouter(prefix="/governance", tags=["Revision Governance"])

@router.get("/conflicts", response_model=List[DocumentConflict])
def get_document_conflicts(
    machine_model: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Scans active approved documents and quality alerts to detect
    conflicting operating limits or contradictory technical parameters.
    """
    return conflict_detector.scan_for_conflicts(db, machine_model=machine_model)

@router.post("/conflicts/resolve")
def resolve_document_conflict(
    req: ConflictResolutionRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("conflict_resolver")),
):
    """
    Records an authorized human resolution for a detected technical conflict.
    """
    conflict = next(
        (
            item
            for item in conflict_detector.scan_for_conflicts(db)
            if item.conflict_id == req.conflict_id
        ),
        None,
    )
    if conflict is None:
        raise HTTPException(status_code=404, detail="Active conflict not found.")
    if conflict.status == "resolved":
        raise HTTPException(status_code=409, detail="This conflict has already been resolved.")
    if req.winning_document_id not in {
        conflict.document_a_id,
        conflict.document_b_id,
    }:
        raise HTTPException(
            status_code=400,
            detail="Select one of the documents involved in this conflict as the governing source.",
        )

    if req.action_taken in {"mark_superseded", "withdraw_conflicting"}:
        require_user_role(user, "document_approver")
        losing_document_id = (
            conflict.document_b_id
            if req.winning_document_id == conflict.document_a_id
            else conflict.document_a_id
        )
        losing_document = (
            db.query(Document)
            .filter(Document.id == losing_document_id)
            .first()
        )
        if losing_document is None:
            raise HTTPException(status_code=409, detail="A conflicting document no longer exists.")
        if req.action_taken == "mark_superseded":
            losing_document.approval_status = "Superseded"
            losing_document.superseded_by_id = req.winning_document_id
        else:
            losing_document.approval_status = "Withdrawn"
            losing_document.superseded_by_id = None

    resolution = ConflictResolution(
        conflict_id=conflict.conflict_id,
        parameter_or_topic=conflict.parameter_or_topic,
        document_a_id=conflict.document_a_id,
        document_b_id=conflict.document_b_id,
        winning_document_id=req.winning_document_id,
        action_taken=req.action_taken,
        resolution_notes=req.resolution_notes,
        resolver=user.subject,
    )
    db.add(resolution)
    db.commit()
    db.refresh(resolution)

    audit_service.log_action(
        db=db,
        action="CONFLICT_RESOLVED",
        actor=user.subject,
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
        "winning_document_id": resolution.winning_document_id,
        "action_taken": resolution.action_taken,
        "message": "Conflict resolution recorded and applied to future conflict scans.",
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
