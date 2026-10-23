import json
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.review import ReviewItem
from app.schemas.review import ReviewItemResponse, ReviewActionRequest
from app.services.audit_service import audit_service

router = APIRouter(prefix="/review", tags=["Expert Review Queue"])

@router.get("/queue", response_model=List[ReviewItemResponse])
def get_review_queue(
    status: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns items requiring human manufacturing expert intervention:
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
    
    result = []
    for it in items:
        details_dict = json.loads(it.details_json) if it.details_json else {}
        resp = ReviewItemResponse(
            id=it.id,
            item_type=it.item_type,
            status=it.status,
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
):
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    item.status = action_req.action
    item.expert_notes = action_req.expert_notes
    item.reviewer = action_req.reviewer_name
    item.resolved_at = datetime.now(timezone.utc)
    db.commit()

    audit_service.log_action(
        db=db,
        action="EXPERT_REVIEW_DECISION",
        actor=action_req.reviewer_name,
        resource_type="review_item",
        resource_id=item.id,
        details={"decision": action_req.action, "notes": action_req.expert_notes},
    )

    return {
        "status": "success",
        "item_id": item.id,
        "action": action_req.action,
        "reviewer": action_req.reviewer_name,
        "message": f"Review item updated to '{action_req.action}' by {action_req.reviewer_name}."
    }
