import time
import json
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.schemas.query import QuestionRequest, GroundedAnswerResponse, Citation, AbstentionReasonEnum, SafetyEscalationInfo
from app.schemas.retrieval import RetrievalQuery, RetrievalModeEnum
from app.retrieval.hybrid import hybrid_retriever
from app.verification.safety_rules import safety_rules
from app.verification.citation_validator import citation_validator
from app.governance.conflict_detector import conflict_detector
from app.llm.provider import llm_provider
from app.models.review import ReviewItem
from app.services.audit_service import audit_service

class QAService:
    """
    Main orchestration service for Grounded Shop Floor Question Answering.
    Enforces revision governance, safety evaluation, conflict detection,
    and verifiable citations.
    """
    def answer_question(
        self,
        db: Session,
        request: QuestionRequest,
        actor: str = "operator"
    ) -> GroundedAnswerResponse:
        start_time = time.perf_counter()

        # Step 1: Safety-Critical Query Evaluation (Deterministic Rules)
        safety_info: SafetyEscalationInfo = safety_rules.evaluate(request.question)
        review_item_id = None

        if safety_info.is_safety_critical and settings.HIGH_RISK_MANDATORY_REVIEW:
            # Model confidence can NEVER bypass this review
            review_item = ReviewItem(
                item_type="safety_critical_query",
                status="pending",
                priority=safety_info.risk_level,
                title=f"Safety Alert: {safety_info.matched_rules[0] if safety_info.matched_rules else 'High Risk Query'}",
                summary=f"Operator query flagged: '{request.question}'",
                details_json=json.dumps({
                    "question": request.question,
                    "matched_rules": safety_info.matched_rules,
                    "escalation_reason": safety_info.escalation_reason,
                    "risk_level": safety_info.risk_level,
                }),
                proposed_action="Do not execute operation. Senior manufacturing safety specialist must review.",
            )
            db.add(review_item)
            db.commit()
            db.refresh(review_item)
            safety_info.review_item_id = review_item.id

            audit_service.log_action(
                db=db,
                action="SAFETY_ESCALATION",
                actor=actor,
                resource_type="query",
                resource_id=review_item.id,
                details={"question": request.question, "risk_level": safety_info.risk_level},
            )

        # Step 2: Retrieve Evidence
        retrieval_query = RetrievalQuery(
            query=request.question,
            mode=request.retrieval_mode,
            top_k=request.top_k,
            filter_approved_only=request.filter_approved_only,
            machine_model=request.machine_model,
        )
        retrieval_res = hybrid_retriever.search(db, retrieval_query)
        retrieved_passages = retrieval_res.results

        # Step 3: Conflict Detection Across Retrieved Passages
        conflicts_detected = conflict_detector.detect_in_retrieved_passages(retrieved_passages)
        if conflicts_detected:
            # Log conflict review item
            conflict_review = ReviewItem(
                item_type="document_conflict",
                status="pending",
                priority="high",
                title="Conflicting Technical Directives in Retrieved Documents",
                summary="; ".join(conflicts_detected),
                details_json=json.dumps({
                    "question": request.question,
                    "conflicts": conflicts_detected,
                    "passages_count": len(retrieved_passages),
                }),
                proposed_action="Route to Quality Engineering for discrepancy reconciliation.",
            )
            db.add(conflict_review)
            db.commit()

        # Step 4: Grounded Answer Synthesis
        raw_answer, raw_citations, abstained, abstention_reason, abstention_explanation = (
            llm_provider.generate_grounded_answer(
                question=request.question,
                retrieved_passages=retrieved_passages,
                conflicts_detected=conflicts_detected,
                is_safety_critical=safety_info.is_safety_critical,
            )
        )

        # Step 5: Validate Citations Against Retrieved Passages
        validated_citations = citation_validator.validate_citations(
            candidate_citations=raw_citations,
            retrieved_passages=retrieved_passages,
        )

        total_latency = (time.perf_counter() - start_time) * 1000
        authoritative_doc_ids = list(set([p.document_id for p in retrieved_passages if p.is_authoritative]))

        # Step 6: Audit Trail
        audit_entry = audit_service.log_action(
            db=db,
            action="QUERY_ANSWERED" if not abstained else "QUERY_ABSTAINED",
            actor=actor,
            resource_type="query",
            details={
                "question": request.question,
                "abstained": abstained,
                "abstention_reason": abstention_reason.value,
                "citations_count": len(validated_citations),
                "retrieved_count": len(retrieved_passages),
                "is_safety_critical": safety_info.is_safety_critical,
                "latency_ms": round(total_latency, 2),
            },
        )

        return GroundedAnswerResponse(
            question=request.question,
            answer=raw_answer,
            abstained=abstained,
            abstention_reason=abstention_reason,
            abstention_explanation=abstention_explanation,
            citations=validated_citations,
            retrieved_passages=retrieved_passages,
            safety_escalation=safety_info,
            conflicts_detected=conflicts_detected,
            authoritative_doc_ids=authoritative_doc_ids,
            retrieval_mode_used=retrieval_res.retrieval_mode,
            provider_used=llm_provider.provider_name,
            latency_ms=round(total_latency, 2),
            audit_log_id=audit_entry.id,
        )

qa_service = QAService()
