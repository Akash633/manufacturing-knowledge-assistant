import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.ingestion.pdf_extractor import pdf_extractor
from app.ingestion.docx_extractor import docx_extractor
from app.ingestion.chunker import chunker

class DocumentParser:
    """
    Coordinates file validation, text extraction, checksum generation,
    and structured chunking for PDF and DOCX files.
    """
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}

    def validate_file(self, file_path: Path) -> Tuple[bool, str]:
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"
        
        ext = file_path.suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(self.ALLOWED_EXTENSIONS)}"

        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            return False, f"File size ({size_mb:.2f} MB) exceeds maximum allowed size ({settings.MAX_FILE_SIZE_MB} MB)"

        return True, "Valid"

    def calculate_checksum(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def parse_document(self, file_path: Path, doc_id: str) -> Dict[str, Any]:
        is_valid, reason = self.validate_file(file_path)
        if not is_valid:
            raise ValueError(f"File validation failed: {reason}")

        checksum = self.calculate_checksum(file_path)
        file_size = file_path.stat().st_size
        ext = file_path.suffix.lower().replace(".", "")

        logger.info(f"Ingesting {ext.upper()} document {file_path.name} (ID: {doc_id})")

        if ext == "pdf":
            extracted_pages = pdf_extractor.extract(file_path, doc_id)
        elif ext == "docx":
            extracted_pages = docx_extractor.extract(file_path, doc_id)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        page_count = len(extracted_pages)
        raw_chunks = chunker.chunk_extracted_pages(doc_id, extracted_pages)

        return {
            "checksum": checksum,
            "file_size_bytes": file_size,
            "file_type": ext,
            "page_count": page_count,
            "extracted_pages": extracted_pages,
            "chunks": raw_chunks,
        }

document_parser = DocumentParser()
