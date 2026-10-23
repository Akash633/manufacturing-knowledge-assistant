import sys
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid

# Add backend directory to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "backend"))

from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.ingestion.parser import document_parser
from app.retrieval.vector import embedding_provider
from app.services.audit_service import audit_service

def seed_database():
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear existing data for clean seed if needed
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.commit()

    corpus_dir = settings.SYNTHETIC_CORPUS_DIR

    docs_meta = [
        {
            "filename": "SOP-CNC-001_RevA_SUPERSEDED.pdf",
            "document_number": "SOP-CNC-001",
            "title": "Standard Operating Procedure: Spindle & Coolant Controls",
            "revision": "Rev A",
            "approval_status": "Superseded",
            "machine_model": "DEMO-CNC-01",
            "section_category": "Standard Operating Procedure",
            "effective_date": datetime(2021, 3, 1, tzinfo=timezone.utc),
            "expiry_date": datetime(2024, 1, 14, tzinfo=timezone.utc),
            "is_superseded": True,
        },
        {
            "filename": "SOP-CNC-001_RevB_APPROVED.pdf",
            "document_number": "SOP-CNC-001",
            "title": "Standard Operating Procedure: Spindle & Coolant Controls",
            "revision": "Rev B",
            "approval_status": "Approved",
            "machine_model": "DEMO-CNC-01",
            "section_category": "Standard Operating Procedure",
            "effective_date": datetime(2024, 1, 15, tzinfo=timezone.utc),
            "expiry_date": None,
            "is_superseded": False,
        },
        {
            "filename": "MR-2024-08_RevA_APPROVED.docx",
            "document_number": "MR-2024-08",
            "title": "Preventive Maintenance & Calibration Report",
            "revision": "Rev A",
            "approval_status": "Approved",
            "machine_model": "DEMO-CNC-01",
            "section_category": "Maintenance",
            "effective_date": datetime(2024, 8, 1, tzinfo=timezone.utc),
            "expiry_date": None,
            "is_superseded": False,
        },
        {
            "filename": "QA-CNC-2024-03_RevA_APPROVED.pdf",
            "document_number": "QA-CNC-2024-03",
            "title": "Quality Alert: Titanium Grade 5 Chatter & Feed Rate Restriction",
            "revision": "Rev A",
            "approval_status": "Approved",
            "machine_model": "DEMO-CNC-01",
            "section_category": "Quality Alert",
            "effective_date": datetime(2024, 3, 10, tzinfo=timezone.utc),
            "expiry_date": None,
            "is_superseded": False,
        },
    ]

    created_docs = {}

    for m in docs_meta:
        file_path = corpus_dir / m["filename"]
        if not file_path.exists():
            logger.error(f"Missing file: {file_path}")
            continue

        doc_id = str(uuid.uuid4())
        parsed = document_parser.parse_document(file_path, doc_id)

        doc = Document(
            id=doc_id,
            document_number=m["document_number"],
            title=m["title"],
            revision=m["revision"],
            approval_status=m["approval_status"],
            machine_model=m["machine_model"],
            section_category=m["section_category"],
            effective_date=m["effective_date"],
            expiry_date=m["expiry_date"],
            file_path=str(file_path),
            file_type=parsed["file_type"],
            file_size_bytes=parsed["file_size_bytes"],
            checksum=parsed["checksum"],
            page_count=parsed["page_count"],
            metadata_json=json.dumps({"synthetic": True, "source_file": m["filename"]}),
            is_synthetic_demo=True,
        )
        db.add(doc)
        db.commit()
        created_docs[m["revision"] + "_" + m["document_number"]] = doc

        # Chunks
        raw_chunks = parsed["chunks"]
        contents = [c["content"] for c in raw_chunks]
        embs = embedding_provider.embed_batch(contents) if contents else []

        db_chunks = []
        for idx, c in enumerate(raw_chunks):
            emb_json = json.dumps(embs[idx]) if idx < len(embs) else None
            db_chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=c["chunk_index"],
                page_number=c["page_number"],
                section_title=c["section_title"],
                content=c["content"],
                token_count=c["token_count"],
                has_images=c["has_images"],
                image_paths_json=c["image_paths_json"],
                ocr_applied=c["ocr_applied"],
                embedding_vector_json=emb_json,
            )
            db_chunks.append(db_chunk)

        db.bulk_save_objects(db_chunks)
        db.commit()
        logger.info(f"Ingested {m['document_number']} ({m['revision']}) with {len(db_chunks)} chunks.")

    # Link Rev A and Rev B superseded relationships
    rev_a = created_docs.get("Rev A_SOP-CNC-001")
    rev_b = created_docs.get("Rev B_SOP-CNC-001")
    if rev_a and rev_b:
        rev_a.superseded_by_id = rev_b.id
        rev_b.supersedes_id = rev_a.id
        db.commit()
        logger.info(f"Linked Rev A superseded by Rev B ({rev_b.id}).")

    audit_service.log_action(
        db=db,
        action="SEED_DATABASE",
        actor="system_initializer",
        resource_type="corpus",
        details={"seeded_documents": len(docs_meta)},
    )

    db.close()
    logger.info("Database seeding complete!")

if __name__ == "__main__":
    seed_database()
