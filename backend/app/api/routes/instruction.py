import json
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_optional_user, require_roles
from app.db.session import get_db
from app.models.instruction import DraftWorkInstruction
from app.schemas.instruction import WorkInstructionCreateRequest, WorkInstructionResponse, InstructionStep
from app.services.instruction_service import instruction_service

router = APIRouter(prefix="/instructions", tags=["Work Instructions"])

@router.post("/draft", response_model=WorkInstructionResponse)
def create_draft_work_instruction(
    req: WorkInstructionCreateRequest,
    db: Session = Depends(get_db),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
):
    """
    Generates a draft work instruction derived strictly from approved shop-floor documentation.
    Must remain unpublished until an authorized specialist approves it.
    """
    try:
        draft = instruction_service.create_draft(
            db,
            req,
            created_by=user.subject if user else "assistant_generator",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _format_instruction_response(draft)

@router.get("", response_model=List[WorkInstructionResponse])
def list_work_instructions(
    machine_model: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(DraftWorkInstruction)
    if machine_model:
        q = q.filter(DraftWorkInstruction.machine_model == machine_model)
    if status:
        q = q.filter(DraftWorkInstruction.status == status)

    items = q.order_by(DraftWorkInstruction.created_at.desc()).all()
    return [_format_instruction_response(it) for it in items]

@router.get("/{instruction_id}", response_model=WorkInstructionResponse)
def get_work_instruction(instruction_id: str, db: Session = Depends(get_db)):
    draft = db.query(DraftWorkInstruction).filter(DraftWorkInstruction.id == instruction_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Work instruction not found")
    return _format_instruction_response(draft)

@router.post("/{instruction_id}/approve", response_model=WorkInstructionResponse)
def approve_work_instruction(
    instruction_id: str,
    comments: str = Body(default="Authorized review recorded.", embed=True),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("instruction_approver")),
):
    """
    Authorized sign-off releasing the draft work instruction to published status.
    """
    try:
        updated = instruction_service.approve_draft(
            db,
            instruction_id,
            user.subject,
            comments,
        )
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(e))

    return _format_instruction_response(updated)

def _format_instruction_response(inst: DraftWorkInstruction) -> WorkInstructionResponse:
    steps_raw = json.loads(inst.steps_json) if inst.steps_json else []
    steps = [InstructionStep(**s) for s in steps_raw]

    return WorkInstructionResponse(
        id=inst.id,
        instruction_number=inst.instruction_number,
        title=inst.title,
        machine_model=inst.machine_model,
        task_summary=inst.task_summary,
        approved_source_doc_ids=json.loads(inst.approved_source_doc_ids_json) if inst.approved_source_doc_ids_json else [],
        steps=steps,
        safety_warnings=json.loads(inst.safety_warnings_json) if inst.safety_warnings_json else [],
        required_ppe=json.loads(inst.required_ppe_json) if inst.required_ppe_json else [],
        status=inst.status,
        is_published=inst.is_published,
        created_by=inst.created_by,
        reviewed_by=inst.reviewed_by,
        review_comments=inst.review_comments,
        reviewed_at=inst.reviewed_at,
        created_at=inst.created_at,
        updated_at=inst.updated_at,
    )
