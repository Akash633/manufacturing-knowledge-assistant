from pathlib import Path
from typing import List, Dict, Any, Tuple
import docx
from app.core.logging import logger

class DOCXExtractor:
    """
    Extracts text, structured sections, and tables from DOCX files using python-docx.
    Estimates logical pages/sections and extracts tabular parameters accurately.
    """
    def extract(self, file_path: Path, doc_id: str) -> List[Dict[str, Any]]:
        extracted_pages: List[Dict[str, Any]] = []

        try:
            doc = docx.Document(str(file_path))
            current_section = "General Overview"
            current_page = 1
            section_blocks: List[str] = []
            page_blocks: List[str] = []

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue

                style_name = paragraph.style.name if paragraph.style else ""
                
                # Check for headings or page breaks
                if "Heading" in style_name or text.isupper() and len(text) < 60:
                    if section_blocks:
                        page_blocks.append(f"### {current_section}\n" + "\n".join(section_blocks))
                        section_blocks = []
                    current_section = text
                else:
                    section_blocks.append(text)

                # Heuristic page split every ~600 words or on explicit page breaks
                total_words = sum(len(b.split()) for b in section_blocks)
                if total_words > 450:
                    page_blocks.append(f"### {current_section}\n" + "\n".join(section_blocks))
                    extracted_pages.append({
                        "page_number": current_page,
                        "text": "\n\n".join(page_blocks),
                        "sections": [(current_section, "\n".join(section_blocks))],
                        "images": [],
                        "preview_url": None,
                    })
                    current_page += 1
                    page_blocks = []
                    section_blocks = []

            # Also extract tables (very common for manufacturing feeds, speeds, maintenance specs)
            for table_idx, table in enumerate(doc.tables):
                table_rows = []
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells]
                    table_rows.append(" | ".join(row_cells))
                
                table_md = "\n".join(table_rows)
                section_blocks.append(f"\n[TABLE {table_idx + 1} SPECIFICATIONS]:\n{table_md}\n")

            if section_blocks or page_blocks:
                page_blocks.append(f"### {current_section}\n" + "\n".join(section_blocks))
                extracted_pages.append({
                    "page_number": current_page,
                    "text": "\n\n".join(page_blocks),
                    "sections": [(current_section, "\n".join(section_blocks))],
                    "images": [],
                    "preview_url": None,
                })

            if not extracted_pages:
                extracted_pages.append({
                    "page_number": 1,
                    "text": "Document contained no extractable text.",
                    "sections": [("Empty", "No text found")],
                    "images": [],
                    "preview_url": None,
                })

        except Exception as e:
            logger.error(f"Error parsing DOCX file {file_path}: {e}")
            raise ValueError(f"Failed to extract DOCX contents: {str(e)}")

        return extracted_pages

docx_extractor = DOCXExtractor()
