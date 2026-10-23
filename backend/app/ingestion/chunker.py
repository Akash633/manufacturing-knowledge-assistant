import re
import json
from typing import List, Dict, Any

class ManufacturingChunker:
    """
    Domain-aware chunker tailored for shop-floor documents, SOPs, and technical manuals.
    Respects page boundaries, section headers, warning/caution blocks, and tolerance tables.
    """
    def __init__(self, target_chunk_size: int = 350, chunk_overlap: int = 50):
        self.target_chunk_size = target_chunk_size # approximate words
        self.chunk_overlap = chunk_overlap

    def chunk_extracted_pages(
        self,
        document_id: str,
        extracted_pages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        chunk_index = 0

        for page in extracted_pages:
            page_number = page["page_number"]
            page_images = page.get("images", [])
            image_relative_urls = [img["relative_url"] for img in page_images]
            sections = page.get("sections", [])
            page_text = page.get("text", "")

            # If page has structured sections, chunk by section
            if sections and len(sections) > 0:
                for section_title, section_body in sections:
                    clean_body = section_body.strip()
                    if not clean_body:
                        continue

                    # Split large section into subchunks if necessary
                    subchunks = self._split_text_blocks(clean_body)
                    for sub in subchunks:
                        token_count = len(sub.split())
                        chunks.append({
                            "chunk_index": chunk_index,
                            "page_number": page_number,
                            "section_title": section_title,
                            "content": f"[{section_title}]\n{sub}",
                            "token_count": token_count,
                            "has_images": len(image_relative_urls) > 0,
                            "image_paths_json": json.dumps(image_relative_urls),
                            "ocr_applied": any(img.get("ocr_info", {}).get("is_ocr_extracted", False) for img in page_images),
                        })
                        chunk_index += 1
            else:
                # Fallback: chunk page text
                if page_text:
                    subchunks = self._split_text_blocks(page_text)
                    for sub in subchunks:
                        token_count = len(sub.split())
                        chunks.append({
                            "chunk_index": chunk_index,
                            "page_number": page_number,
                            "section_title": f"Page {page_number}",
                            "content": sub,
                            "token_count": token_count,
                            "has_images": len(image_relative_urls) > 0,
                            "image_paths_json": json.dumps(image_relative_urls),
                            "ocr_applied": False,
                        })
                        chunk_index += 1

        return chunks

    def _split_text_blocks(self, text: str) -> List[str]:
        # Split by paragraph breaks first
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return [text] if text.strip() else []

        chunks: List[str] = []
        current_chunk_words: List[str] = []

        for p in paragraphs:
            p_words = p.split()
            # If paragraph itself is huge, break into sentences
            if len(p_words) > self.target_chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", p)
                for s in sentences:
                    s_words = s.split()
                    if len(current_chunk_words) + len(s_words) > self.target_chunk_size and current_chunk_words:
                        chunks.append(" ".join(current_chunk_words))
                        # Retain overlap
                        overlap_words = current_chunk_words[-self.chunk_overlap:] if len(current_chunk_words) > self.chunk_overlap else []
                        current_chunk_words = overlap_words + s_words
                    else:
                        current_chunk_words.extend(s_words)
            else:
                if len(current_chunk_words) + len(p_words) > self.target_chunk_size and current_chunk_words:
                    chunks.append(" ".join(current_chunk_words))
                    overlap_words = current_chunk_words[-self.chunk_overlap:] if len(current_chunk_words) > self.chunk_overlap else []
                    current_chunk_words = overlap_words + p_words
                else:
                    current_chunk_words.extend(p_words)

        if current_chunk_words:
            chunks.append(" ".join(current_chunk_words))

        return chunks

chunker = ManufacturingChunker()
