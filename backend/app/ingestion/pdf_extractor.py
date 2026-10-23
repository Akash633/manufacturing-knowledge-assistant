from pathlib import Path
from typing import List, Dict, Any, Tuple
import re
from app.core.logging import logger
from app.multimodal.image_manager import image_manager

class PDFExtractor:
    """
    Extracts structured text, headings, and images from PDF documents using PyMuPDF.
    Preserves exact page numbers (1-indexed) and links images to their origin page.
    """
    def extract(self, file_path: Path, doc_id: str) -> List[Dict[str, Any]]:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        extracted_pages: List[Dict[str, Any]] = []

        try:
            doc = fitz.open(str(file_path))
            for page_idx in range(len(doc)):
                page_num = page_idx + 1
                page = doc[page_idx]

                # Extract text blocks
                text = page.get_text("text").strip()
                
                # Extract embedded images and page preview
                images = image_manager.extract_images_from_pdf_page(doc_id, page_idx, page, doc)
                page_preview_url = image_manager.render_page_preview(doc_id, page_idx, page)

                # Identify potential section headings from text or font size blocks
                detected_sections = self._detect_sections_from_page(page)

                extracted_pages.append({
                    "page_number": page_num,
                    "text": text,
                    "sections": detected_sections,
                    "images": images,
                    "preview_url": page_preview_url,
                })
            doc.close()
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {e}")
            raise ValueError(f"Failed to extract PDF contents: {str(e)}")

        return extracted_pages

    def _detect_sections_from_page(self, page: Any) -> List[Tuple[str, str]]:
        """
        Detect section titles and corresponding text blocks from PyMuPDF dict blocks.
        """
        sections: List[Tuple[str, str]] = []
        try:
            blocks = page.get_text("dict").get("blocks", [])
            current_section = "General"
            current_lines = []

            for b in blocks:
                if "lines" in b:
                    for line in b["lines"]:
                        spans = line.get("spans", [])
                        line_text = "".join(span.get("text", "") for span in spans).strip()
                        if not line_text:
                            continue
                        
                        # Heading heuristic: large font size or uppercase/numbered header pattern
                        is_heading = False
                        max_font_size = max([span.get("size", 10) for span in spans], default=10)
                        if max_font_size >= 12.0 or re.match(r"^(\d+\.|\bSECTION\b|\bSTEP\b|\bPROCEDURE\b|\bMAINTENANCE\b)", line_text, re.IGNORECASE):
                            is_heading = True

                        if is_heading and len(line_text) < 100:
                            if current_lines:
                                sections.append((current_section, "\n".join(current_lines)))
                                current_lines = []
                            current_section = line_text
                        else:
                            current_lines.append(line_text)

            if current_lines:
                sections.append((current_section, "\n".join(current_lines)))
        except Exception as e:
            logger.debug(f"Block analysis fallback for page: {e}")
            sections.append(("General", page.get_text("text").strip()))

        return sections

pdf_extractor = PDFExtractor()
