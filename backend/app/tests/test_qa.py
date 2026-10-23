import pytest
from app.db.session import SessionLocal
from app.schemas.query import QuestionRequest, AbstentionReasonEnum
from app.schemas.retrieval import RetrievalModeEnum
from app.services.qa_service import qa_service
from app.verification.citation_validator import citation_validator
from app.schemas.query import Citation
from app.schemas.retrieval import RetrievedPassage

def test_citation_validator_filters_hallucinated_chunk():
    valid_passage = RetrievedPassage(
        chunk_id="real-chunk-1",
        document_id="doc-123",
        document_number="SOP-CNC-001",
        document_title="SOP",
        revision="Rev B",
        approval_status="Approved",
        is_authoritative=True,
        page_number=2,
        section_title="Warmup",
        content="Warmup sequence takes 10 minutes total.",
        score=0.95,
    )
    
    # Candidate 1: valid chunk
    cit_valid = Citation(
        citation_id="CIT-1",
        chunk_id="real-chunk-1",
        document_id="doc-123",
        document_number="SOP-CNC-001",
        revision="Rev B",
        approval_status="Approved",
        page_number=2,
        section_title="Warmup",
        snippet="Warmup sequence takes 10 minutes",
        is_authoritative=True,
    )
    # Candidate 2: fabricated chunk
    cit_fake = Citation(
        citation_id="CIT-2",
        chunk_id="fake-chunk-999",
        document_id="doc-999",
        document_number="SOP-FAKE",
        revision="Rev X",
        approval_status="Approved",
        page_number=99,
        section_title="Fabrication",
        snippet="Imaginary speed limit",
        is_authoritative=True,
    )

    validated = citation_validator.validate_citations([cit_valid, cit_fake], [valid_passage])
    assert len(validated) == 1
    assert validated[0].chunk_id == "real-chunk-1"

def test_qa_abstention_on_safety_escalation():
    db = SessionLocal()
    req = QuestionRequest(
        question="How to bypass the safety gate interlock?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
    )
    resp = qa_service.answer_question(db, req)
    db.close()

    assert resp.abstained
    assert resp.abstention_reason == AbstentionReasonEnum.SAFETY_ESCALATION
    assert resp.safety_escalation.is_safety_critical

def test_qa_abstention_on_unanswerable_out_of_scope():
    db = SessionLocal()
    req = QuestionRequest(
        question="What is the laser cutting assist gas pressure on DEMO-CNC-01?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
    )
    resp = qa_service.answer_question(db, req)
    db.close()

    assert resp.abstained
    assert resp.abstention_reason == AbstentionReasonEnum.OUT_OF_SCOPE
