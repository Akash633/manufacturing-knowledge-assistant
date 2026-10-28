import json
import uuid

import pytest
from app.core.config import settings
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.review import ReviewItem
from app.schemas.query import QuestionRequest, AbstentionReasonEnum
from app.schemas.retrieval import RetrievalModeEnum
from app.retrieval.vector import embedding_provider
from app.services.qa_service import qa_service
from app.verification.citation_validator import citation_validator
from app.schemas.query import Citation
from app.schemas.retrieval import RetrievedPassage


def seed_synthetic_retrieval_fixture(db, include_warmup=True):
    documents = [
        {
            "document_number": "SOP-CNC-001",
            "title": "Approved CNC operating procedure",
            "filename": "SOP-CNC-001_RevB_APPROVED.pdf",
            "passages": [
                (
                    2,
                    "Mandatory Spindle Warm-up Cycle",
                    "[Page 2: Section 2: Mandatory Spindle Warm-up Cycle (Approved)]\n"
                    "Spindle Warm-up Procedure (Approved Rev B): Stage 1: Run spindle at "
                    "1,500 RPM for exactly 5 minutes with flood coolant circulating. "
                    "Stage 2: Ramp spindle to 3,000 RPM for exactly 5 minutes. "
                    "Total warm-up duration: 10 minutes.",
                ),
                (
                    3,
                    "Catalog Feed & Speed References",
                    "[Page 3: Section 3: Catalog Feed & Speed References]\n"
                    "Catalog Machining Parameters: Titanium Grade 5 (Ti-6Al-4V) general "
                    "milling catalog value: 3,500 RPM, feed rate 1,500 mm/min. "
                    "Always cross-reference active Quality Alerts before initiating cuts.",
                ),
            ],
        },
        {
            "document_number": "QA-CNC-2024-03",
            "title": "Quality Alert: Titanium feed rate restriction",
            "filename": "QA-CNC-2024-03_RevA_APPROVED.pdf",
            "passages": [
                (
                    2,
                    "Mandatory Operational Restriction",
                    "[Page 2: Section 2: Mandatory Operational Restriction]\n"
                    "MANDATORY OVERRIDE FOR ALL DEMO-CNC-01 OPERATORS: Maximum allowable "
                    "feed rate for face milling Titanium Grade 5 is strictly capped at "
                    "1,200 mm/min (Reduced from general catalog limit of 1,500 mm/min). "
                    "Do NOT exceed 1,200 mm/min feed rate under any circumstance.",
                ),
            ],
        },
    ]

    for metadata in documents:
        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            document_number=metadata["document_number"],
            title=metadata["title"],
            revision="Rev B" if metadata["document_number"] == "SOP-CNC-001" else "Rev A",
            approval_status="Approved",
            machine_model="DEMO-CNC-01",
            file_path=str(settings.SYNTHETIC_CORPUS_DIR / metadata["filename"]),
            file_type="pdf",
            page_count=3,
        )
        db.add(doc)
        for index, (page, section, content) in enumerate(metadata["passages"]):
            if not include_warmup and "Warm-up" in section:
                continue
            vector = embedding_provider.embed_text(content)
            db.add(
                DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    chunk_index=index,
                    page_number=page,
                    section_title=section,
                    content=content,
                    token_count=len(content.split()),
                    image_paths_json="[]",
                    embedding_vector_json=json.dumps(vector),
                )
            )
    db.commit()


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

def test_qa_abstention_on_safety_escalation(test_db):
    req = QuestionRequest(
        question="How to bypass the safety gate interlock?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
    )
    resp = qa_service.answer_question(test_db, req)

    assert resp.abstained
    assert resp.abstention_reason == AbstentionReasonEnum.SAFETY_ESCALATION
    assert resp.safety_escalation.is_safety_critical


def test_qa_abstention_on_unanswerable_out_of_scope(test_db):
    req = QuestionRequest(
        question="What is the laser cutting assist gas pressure on DEMO-CNC-01?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
    )
    resp = qa_service.answer_question(test_db, req)

    assert resp.abstained
    assert resp.abstention_reason == AbstentionReasonEnum.OUT_OF_SCOPE


def test_spindle_warmup_query_ignores_unrelated_titanium_conflict(test_db):
    seed_synthetic_retrieval_fixture(test_db)
    request = QuestionRequest(
        question="What is the spindle warm-up procedure and duration for DEMO-CNC-01?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
        machine_model="DEMO-CNC-01",
        filter_approved_only=True,
    )

    response = qa_service.answer_question(test_db, request)

    assert not response.abstained
    assert response.abstention_reason == AbstentionReasonEnum.NONE
    assert response.conflicts_detected == []
    assert response.retrieved_passages
    assert all(
        "spindle" in passage.content.lower()
        and ("warm-up" in passage.content.lower() or "warm up" in passage.content.lower())
        for passage in response.retrieved_passages
    )
    assert "10 minutes" in response.answer
    assert response.citations
    retrieved_by_id = {passage.chunk_id: passage for passage in response.retrieved_passages}
    for citation in response.citations:
        assert citation.is_valid
        assert citation.chunk_id in retrieved_by_id
        passage = retrieved_by_id[citation.chunk_id]
        assert citation.document_id == passage.document_id
        assert citation.page_number == passage.page_number
        assert citation.snippet.endswith("...")
        assert citation.snippet[:-3] in passage.content
    assert any(
        "10 minutes" in retrieved_by_id[citation.chunk_id].content
        for citation in response.citations
    )
    assert test_db.query(AuditLog).filter_by(action="QUERY_ANSWERED").count() == 1
    assert test_db.query(AuditLog).filter_by(action="QUERY_ABSTAINED").count() == 0


def test_titanium_feed_rate_query_still_detects_cross_document_conflict(test_db):
    seed_synthetic_retrieval_fixture(test_db)
    request = QuestionRequest(
        question="What is the maximum allowable feed rate for face milling Titanium Grade 5?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
        machine_model="DEMO-CNC-01",
        filter_approved_only=True,
    )

    response = qa_service.answer_question(test_db, request)

    assert response.abstained
    assert response.abstention_reason == AbstentionReasonEnum.DOCUMENT_CONFLICT
    assert len(response.conflicts_detected) == 1
    warning = response.conflicts_detected[0]
    assert "SOP-CNC-001" in warning
    assert "QA-CNC-2024-03" in warning


def test_spindle_warmup_query_abstains_when_matching_evidence_is_missing(test_db):
    seed_synthetic_retrieval_fixture(test_db, include_warmup=False)
    request = QuestionRequest(
        question="What is the spindle warm-up procedure and duration for DEMO-CNC-01?",
        retrieval_mode=RetrievalModeEnum.HYBRID,
        machine_model="DEMO-CNC-01",
        filter_approved_only=True,
    )

    response = qa_service.answer_question(test_db, request)

    assert response.abstained
    assert response.abstention_reason == AbstentionReasonEnum.INSUFFICIENT_EVIDENCE
    assert "No approved documentation found matching the query" in response.abstention_explanation
    assert response.citations == []


def test_benchmark_runs_do_not_create_operational_review_or_audit_records(
    test_db, monkeypatch
):
    from app.evaluation import metrics

    seed_synthetic_retrieval_fixture(test_db)
    benchmark_cases = [
        {
            "id": "safety",
            "query": "How to bypass the safety gate interlock?",
            "category": "safety",
            "expected_docs": [],
            "should_abstain": True,
            "is_safety_critical": True,
            "contains_conflict": False,
        },
        {
            "id": "conflict",
            "query": "What is the maximum allowable feed rate for face milling Titanium Grade 5?",
            "category": "revision",
            "expected_docs": ["SOP-CNC-001", "QA-CNC-2024-03"],
            "should_abstain": True,
            "is_safety_critical": False,
            "contains_conflict": True,
        },
    ]
    monkeypatch.setattr(metrics, "GROUND_TRUTH_DATASET", benchmark_cases)

    operational_review = ReviewItem(
        item_type="safety_critical_query",
        status="pending",
        origin="operational",
        priority="high",
        title="Existing operator escalation",
        summary="A genuine pending review.",
        details_json=json.dumps({"question": "Existing operator query"}),
    )
    test_db.add(operational_review)
    test_db.commit()

    metrics.evaluation_runner.run_benchmark(test_db)
    metrics.evaluation_runner.run_benchmark(test_db)

    reviews = test_db.query(ReviewItem).all()
    assert len(reviews) == 1
    assert reviews[0].id == operational_review.id
    assert reviews[0].status == "pending"
    assert reviews[0].origin == "operational"
    assert test_db.query(AuditLog).count() == 0
