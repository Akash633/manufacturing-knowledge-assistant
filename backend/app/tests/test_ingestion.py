import pytest
from pathlib import Path
from app.ingestion.parser import document_parser
from app.core.config import settings

def test_file_validation_rejects_unsupported_extension(tmp_path):
    fake_txt = tmp_path / "instructions.txt"
    fake_txt.write_text("Hello world")
    is_valid, reason = document_parser.validate_file(fake_txt)
    assert not is_valid
    assert "Unsupported file extension" in reason

def test_checksum_calculation(tmp_path):
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(b"manufacturing specification binary data")
    checksum = document_parser.calculate_checksum(test_file)
    assert len(checksum) == 64
    assert isinstance(checksum, str)

def test_parse_synthetic_pdf():
    pdf_path = settings.SYNTHETIC_CORPUS_DIR / "SOP-CNC-001_RevB_APPROVED.pdf"
    assert pdf_path.exists(), "Synthetic test PDF must exist"
    
    parsed = document_parser.parse_document(pdf_path, doc_id="test-doc-id")
    assert parsed["file_type"] == "pdf"
    assert parsed["page_count"] >= 2
    assert len(parsed["chunks"]) > 0
    
    # Check that chunks have page numbers and section titles
    first_chunk = parsed["chunks"][0]
    assert first_chunk["page_number"] >= 1
    assert "section_title" in first_chunk
    assert len(first_chunk["content"]) > 10
