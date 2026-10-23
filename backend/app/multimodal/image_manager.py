import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import io
from app.core.config import settings
from app.core.logging import logger
from app.multimodal.ocr import extract_ocr_text

class ImageManager:
    """
    Manages document page snapshots and embedded image extraction.
    Links extracted images to document ID, page number, and section titles.
    """
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.IMAGE_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_images_from_pdf_page(
        self,
        doc_id: str,
        page_index: int, # 0-indexed
        page_obj: Any,
        pdf_doc: Any,
    ) -> List[Dict[str, Any]]:
        """
        Extract embedded raster images from a PDF page using PyMuPDF.
        """
        extracted = []
        page_num = page_index + 1

        try:
            image_list = page_obj.get_images(full=True)
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = pdf_doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")

                filename = f"{doc_id}_p{page_num}_img{img_index + 1}.{image_ext}"
                target_path = self.output_dir / filename
                
                with open(target_path, "wb") as f:
                    f.write(image_bytes)

                # Attempt OCR on the image
                ocr_info = extract_ocr_text(target_path)

                extracted.append({
                    "filename": filename,
                    "relative_url": f"/api/documents/images/{filename}",
                    "file_path": str(target_path),
                    "page_number": page_num,
                    "image_index": img_index + 1,
                    "ocr_info": ocr_info,
                })
        except Exception as e:
            logger.warning(f"Failed extracting embedded images from page {page_num} of {doc_id}: {e}")

        return extracted

    def render_page_preview(self, doc_id: str, page_index: int, page_obj: Any) -> Optional[str]:
        """
        Render a PDF page to a PNG image for full-page evidence inspection.
        """
        page_num = page_index + 1
        try:
            pix = page_obj.get_pixmap(dpi=150)
            filename = f"{doc_id}_page_{page_num}_preview.png"
            target_path = self.output_dir / filename
            pix.save(str(target_path))
            return f"/api/documents/images/{filename}"
        except Exception as e:
            logger.warning(f"Could not render page preview for page {page_num} of {doc_id}: {e}")
            return None

image_manager = ImageManager()
