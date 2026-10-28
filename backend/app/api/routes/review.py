import json
from typing import List, Literal, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_roles
from app.db.session import get_db
from app.models.review import ReviewItem
from app.schemas.review import ReviewItemResponse, ReviewActionRequest
from app.services.audit_service import audit_service
from app.services.review_origin import classify_review_origins

router = APIRouter(prefix="/review", tags=["Expert Review Queue"])

@router.get("/queue", response_model=List[ReviewItemResponse])
def get_review_queue(
    status: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    origin: Literal["operational", "benchmark", "all"] = Query("operational"),
    db: Session = Depends(get_db),
):
    """
    Returns operational review items by default, with retained benchmark history
    available through the origin filter:
    - Safety-critical queries flagged by deterministic rules
    - Document parameter conflicts
    - Draft work instructions pending authorization
    """
    q = db.query(ReviewItem)
    if status:
        q = q.filter(ReviewItem.status == status)
    if item_type:
        q = q.filter(ReviewItem.item_type == item_type)

    items = q.order_by(ReviewItem.created_at.desc()).all()
    origins = classify_review_origins(db, items)
    if origin == "benchmark":
        items = [item for item in items if origins[item.id].value == "benchmark"]
    elif origin == "operational":
        items = [item for item in items if origins[item.id].value != "benchmark"]

    result = []
    for it in items:
        details_dict = json.loads(it.details_json) if it.details_json else {}
        item_origin = origins[it.id]
        resp = ReviewItemResponse(
            id=it.id,
            item_type=it.item_type,
            status=it.status,
            origin=item_origin.value,
            origin_evidence=item_origin.evidence,
            priority=it.priority,
            title=it.title,
            summary=it.summary,
            details=details_dict,
            proposed_action=it.proposed_action,
            expert_notes=it.expert_notes,
            reviewer=it.reviewer,
            resolved_at=it.resolved_at,
            created_at=it.created_at,
        )
        result.append(resp)

    return result

@router.post("/{item_id}/action")
def take_review_action(
    item_id: str,
    action_req: ReviewActionRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("expert_reviewer")),
):
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item_origin = classify_review_origins(db, [item])[item.id]
    if item_origin.value == "benchmark":
        raise HTTPException(
            status_code=409,
            detail="Evaluation-generated review history cannot be actioned as an operational task.",
        )
    if item.status != "pending":
        raise HTTPException(status_code=409, detail="This review item has already been actioned.")

    item.status = action_req.action
    item.expert_notes = action_req.expert_notes
    item.reviewer = user.subject
    item.resolved_at = datetime.now(timezone.utc)
    db.commit()

    audit_service.log_action(
        db=db,
        action="EXPERT_REVIEW_DECISION",
        actor=user.subject,
        resource_type="review_item",
        resource_id=item.id,
        details={"decision": action_req.action, "notes": action_req.expert_notes},
    )

    return {
        "status": "success",
        "item_id": item.id,
        "action": action_req.action,
        "reviewer": user.subject,
        "message": f"Review item updated to '{action_req.action}' by {user.subject}."
    }
