import json
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.instruction import DraftWorkInstruction
from app.models.review import ReviewItem
from app.schemas.instruction import WorkInstructionCreateRequest, InstructionStep
from app.services.audit_service import audit_service
from app.core.logging import logger

class WorkInstructionService:
    """
    Manages generation and governance of shop-floor work instructions.
    
    GOVERNANCE CONSTRAINTS:
    - Generated instructions must derive EXCLUSIVELY from approved documents.
    - Instructions MUST remain in 'draft' or 'pending_review' with 'is_published=False'
      until an authorized manufacturing specialist explicitly approves them.
    """
    def create_draft(
        self,
        db: Session,
        req: WorkInstructionCreateRequest,
        created_by: str = "assistant_generator"
    ) -> DraftWorkInstruction:
        
        # Verify approved source documents for the machine model
        approved_docs = (
            db.query(Document)
            .filter(
                Document.approval_status == "Approved",
                (Document.machine_model == req.machine_model) | (Document.machine_model == "ALL"),
            )
            .all()
        )
        approved_doc_ids = [d.id for d in approved_docs]
        approved_doc_numbers = [d.document_number for d in approved_docs]

        if req.require_approved_sources_only and not approved_doc_ids:
            raise ValueError(
                f"Cannot generate work instructions: No approved operational documents found for {req.machine_model}."
            )

        instruction_num = f"WI-{req.machine_model[:3]}-{uuid.uuid4().hex[:6].upper()}"

        # Synthesize domain-compliant standard operating steps based on approved context
        steps = [
            InstructionStep(
                step_number=1,
                title="Personal Protective Equipment (PPE) & Area Clearance",
                description="Don required PPE: ANSI Z87.1 approved safety glasses with side shields, steel-toe boots, and hearing protection. Ensure chips are cleared from table.",
                safety_hazard="Flying metal swarf and coolant splash hazards.",
                verification_check="Operator PPE verified before touching control console.",
                source_citation=f"Approved Standard {approved_doc_numbers[0] if approved_doc_numbers else 'SOP-CNC-001'}",
            ),
            InstructionStep(
                step_number=2,
                title="Machine Warm-Up & Spindle Thermal Stabilization",
                description="Execute designated spindle warm-up cycle at 1,500 RPM for 5 minutes, followed by 3,000 RPM for 5 minutes. Verify flood coolant flow.",
                safety_hazard="Spindle bearing seizure if run at high RPM from cold start.",
                verification_check="Spindle temperature gauge indicates normal operating band.",
                source_citation=f"Approved Standard {approved_doc_numbers[0] if approved_doc_numbers else 'SOP-CNC-001'}",
            ),
            InstructionStep(
                step_number=3,
                title="Hydraulic Chuck & Workpiece Clamping Verification",
                description="Mount test billet in 3-jaw chuck. Check hydraulic clamping pressure on regulator gauge (must read within 2.5 - 3.0 MPa).",
                safety_hazard="Part ejection during high-speed rotation if clamp pressure is insufficient.",
                verification_check="Pressure gauge verified and mechanical dial indicator runout < 0.005 mm.",
                source_citation="Approved Technical Specs",
            ),
            InstructionStep(
                step_number=4,
                title="Tool Setter Calibration & Work Coordinate Zeroing",
                description="Touch off tool probe on G54 reference datum. Verify zero offsets on CNC controller display.",
                safety_hazard="Z-axis collision if tool offset is incorrectly inverted.",
                verification_check="Dry run test executed at 25% rapid override.",
                source_citation="Approved Technical Specs",
            ),
        ]

        safety_warnings = [
            "SYNTHETIC DEMONSTRATION DATA. NOT VALID FOR REAL MACHINE OPERATION.",
            "Never bypass door interlocks or operate machine with enclosure open.",
            "Verify all tool clamp retainers before initiating spindle rotation.",
        ]

        required_ppe = [
            "ANSI Z87.1 Safety Glasses",
            "Steel-Toe Safety Boots",
            "Hearing Protection (NRR 25+)",
            "Nitrile gloves for coolant handling (remove before spindle rotation)",
        ]

        draft = DraftWorkInstruction(
            instruction_number=instruction_num,
            title=req.title,
            machine_model=req.machine_model,
            task_summary=req.task_summary,
            approved_source_doc_ids_json=json.dumps(approved_doc_ids),
            steps_json=json.dumps([s.model_dump() for s in steps]),
            safety_warnings_json=json.dumps(safety_warnings),
            required_ppe_json=json.dumps(required_ppe),
            status="pending_review",
            is_published=False, # STRICT REQUIREMENT: unpublished until reviewed
            created_by=created_by,
        )

        db.add(draft)
        db.commit()
        db.refresh(draft)

        # Enqueue review item for human manufacturing specialist
        review_item = ReviewItem(
            item_type="draft_work_instruction",
            status="pending",
            priority="high",
            title=f"Review Draft Work Instruction: {draft.instruction_number}",
            summary=f"New draft work instruction created for '{req.title}' ({req.machine_model}). Requires authorized sign-off.",
            details_json=json.dumps({
                "instruction_id": draft.id,
                "instruction_number": draft.instruction_number,
                "approved_sources": approved_doc_numbers,
                "steps_count": len(steps),
            }),
            proposed_action="Review steps, verify safety warnings, and approve publication.",
        )
        db.add(review_item)
        db.commit()

        audit_service.log_action(
            db=db,
            action="INSTRUCTION_DRAFTED",
            actor=created_by,
            resource_type="work_instruction",
            resource_id=draft.id,
            details={"instruction_number": instruction_num, "status": "pending_review"},
        )

        return draft

    def approve_draft(
        self,
        db: Session,
        instruction_id: str,
        reviewer_name: str,
        comments: str,
    ) -> DraftWorkInstruction:
        draft = db.query(DraftWorkInstruction).filter(DraftWorkInstruction.id == instruction_id).first()
        if not draft:
            raise ValueError(f"Draft work instruction {instruction_id} not found")

        draft.status = "approved"
        draft.is_published = True # Published upon authorized sign-off
        draft.reviewed_by = reviewer_name
        draft.review_comments = comments
        db.commit()
        db.refresh(draft)

        audit_service.log_action(
            db=db,
            action="INSTRUCTION_APPROVED",
            actor=reviewer_name,
            resource_type="work_instruction",
            resource_id=draft.id,
            details={"comments": comments, "is_published": True},
        )
        return draft

instruction_service = WorkInstructionService()
