import pytest
from datetime import datetime, timezone, timedelta
from app.models.document import Document
from app.governance.revision_rules import revision_governance
from app.governance.conflict_detector import conflict_detector
from app.schemas.retrieval import RetrievedPassage

def test_revision_governance_rules():
    now = datetime.now(timezone.utc)

    # 1. Draft document is NOT authoritative
    draft_doc = Document(
        document_number="SOP-TEST",
        title="Test SOP",
        revision="Rev C",
        approval_status="Draft",
        file_path="/dummy",
        file_type="pdf",
    )
    res_draft = revision_governance.evaluate_authority(draft_doc, now=now)
    assert not res_draft.is_authoritative
    assert "Draft" in res_draft.reason

    # 2. Approved document in future is NOT yet effective
    future_doc = Document(
        document_number="SOP-TEST",
        title="Test SOP",
        revision="Rev D",
        approval_status="Approved",
        effective_date=now + timedelta(days=5),
        file_path="/dummy",
        file_type="pdf",
    )
    res_future = revision_governance.evaluate_authority(future_doc, now=now)
    assert not res_future.is_authoritative
    assert res_future.status == "Not Yet Effective"

    # 3. Superseded document is NOT authoritative even if status says approved
    superseded_doc = Document(
        document_number="SOP-TEST",
        title="Test SOP",
        revision="Rev A",
        approval_status="Approved",
        superseded_by_id="newer-id-123",
        file_path="/dummy",
        file_type="pdf",
    )
    res_sup = revision_governance.evaluate_authority(superseded_doc, now=now)
    assert not res_sup.is_authoritative
    assert "superseded" in res_sup.reason.lower()

    # 4. Active approved document is authoritative
    active_doc = Document(
        document_number="SOP-TEST",
        title="Test SOP",
        revision="Rev B",
        approval_status="Approved",
        effective_date=now - timedelta(days=10),
        file_path="/dummy",
        file_type="pdf",
    )
    res_active = revision_governance.evaluate_authority(active_doc, now=now)
    assert res_active.is_authoritative
    assert res_active.status == "Approved"

def test_conflict_detection_in_retrieved_passages():
    p1 = RetrievedPassage(
        chunk_id="c1",
        document_id="d1",
        document_number="SOP-CNC-001",
        document_title="SOP",
        revision="Rev B",
        approval_status="Approved",
        is_authoritative=True,
        page_number=3,
        section_title="Feeds",
        content="General catalog parameter lists 1500 mm/min feed rate for Titanium Grade 5.",
        score=0.9,
    )
    p2 = RetrievedPassage(
        chunk_id="c2",
        document_id="d2",
        document_number="QA-CNC-2024-03",
        document_title="Quality Alert",
        revision="Rev A",
        approval_status="Approved",
        is_authoritative=True,
        page_number=2,
        section_title="Override",
        content="Maximum allowable feed rate for face milling Titanium Grade 5 is strictly capped at 1200 mm/min.",
        score=0.88,
    )
    warnings = conflict_detector.detect_in_retrieved_passages([p1, p2])
    assert len(warnings) > 0
    assert "OPERATIONAL CONFLICT" in warnings[0]
