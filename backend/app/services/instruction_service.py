import json
import re
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.instruction import DraftWorkInstruction
from app.models.review import ReviewItem
from app.schemas.instruction import WorkInstructionCreateRequest, InstructionStep
from app.schemas.retrieval import RetrievalQuery
from app.retrieval.hybrid import hybrid_retriever
from app.services.audit_service import audit_service

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
        query_text = " ".join(
            part for part in (req.title, req.target_operation, req.task_summary) if part
        )
        retrieval = hybrid_retriever.search(
            db,
            RetrievalQuery(
                query=query_text[:500],
                top_k=20,
                filter_approved_only=True,
                machine_model=req.machine_model,
            ),
        )
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "in", "into", "is", "of", "on", "or", "the", "to", "with",
        }
        query_terms = {
            token
            for token in re.findall(r"[a-z0-9]+", query_text.lower())
            if token not in stop_words and token not in {"demo", "cnc"}
        }
        minimum_matches = min(2, len(query_terms))
        evidence = [
            passage
            for passage in retrieval.results
            if query_terms and passage.is_authoritative
            and len(
                query_terms.intersection(
                    re.findall(r"[a-z0-9]+", passage.content.lower())
                )
            ) >= minimum_matches
        ]

        if req.require_approved_sources_only and not evidence:
            raise ValueError(
                f"Cannot create a draft: no approved evidence matched the requested task for {req.machine_model}."
            )

        instruction_num = f"WI-{req.machine_model[:3]}-{uuid.uuid4().hex[:6].upper()}"
        evidence = evidence[:5]
        approved_doc_ids = list(dict.fromkeys(passage.document_id for passage in evidence))
        approved_doc_numbers = list(dict.fromkeys(passage.document_number for passage in evidence))
        steps = [
            InstructionStep(
                step_number=index,
                title=(
                    f"Source evidence: {passage.document_number} {passage.revision}, "
                    f"page {passage.page_number}"
                ),
                description=passage.content,
                verification_check="Reviewer must verify this excerpt against the cited source before approval.",
                source_citation=(
                    f"{passage.document_number} ({passage.revision}), "
                    f"page {passage.page_number}, chunk {passage.chunk_id}"
                ),
            )
            for index, passage in enumerate(evidence, start=1)
        ]

        safety_warnings = [
            "Draft evidence summary only; it does not authorize machine operation.",
            "A qualified reviewer must validate each cited source and all safety controls before approval.",
        ]

        draft = DraftWorkInstruction(
            instruction_number=instruction_num,
            title=req.title,
            machine_model=req.machine_model,
            task_summary=req.task_summary,
            approved_source_doc_ids_json=json.dumps(approved_doc_ids),
            steps_json=json.dumps([s.model_dump() for s in steps]),
            safety_warnings_json=json.dumps(safety_warnings),
            required_ppe_json=json.dumps([]),
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
            origin="operational",
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
        if draft.is_published or draft.status != "pending_review":
            raise ValueError(f"Work instruction {instruction_id} has already been reviewed.")

        draft.status = "approved"
        draft.is_published = True # Published upon authorized sign-off
        draft.reviewed_by = reviewer_name
        draft.review_comments = comments
        review_items = (
            db.query(ReviewItem)
            .filter(
                ReviewItem.item_type == "draft_work_instruction",
                ReviewItem.status == "pending",
            )
            .all()
        )
        for item in review_items:
            details = json.loads(item.details_json) if item.details_json else {}
            if details.get("instruction_id") == draft.id:
                item.status = "approved"
                item.expert_notes = comments
                item.reviewer = reviewer_name
                item.resolved_at = datetime.now(timezone.utc)
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
