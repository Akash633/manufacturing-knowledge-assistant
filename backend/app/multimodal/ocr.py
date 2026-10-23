from pathlib import Path
from typing import Optional, Dict, Any
from app.core.logging import logger

def extract_ocr_text(image_path: Path) -> Dict[str, Any]:
    """
    Extract OCR text from a document image when OCR engine is available.
    
    IMPORTANT ARCHITECTURAL NOTICE:
    This function implements optical character recognition (OCR) only.
    It does NOT provide native visual understanding or spatial reasoning.
    The system explicitly reports `is_visual_understanding: False` to maintain
    truthfulness and prevent hallucinating multimodal reasoning.
    """
    if not image_path.exists():
        return {
            "text": "",
            "confidence": 0.0,
            "engine": "none",
            "is_ocr_extracted": False,
            "is_visual_understanding": False,
            "note": "Image file not found on disk."
        }

    # Attempt pytesseract if available
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img).strip()
        return {
            "text": text,
            "confidence": 0.85 if text else 0.0,
            "engine": "tesseract",
            "is_ocr_extracted": bool(text),
            "is_visual_understanding": False,
            "note": "Text extracted via optical character recognition. Visual diagram semantics require expert operator verification."
        }
    except Exception as e:
        logger.debug(f"pytesseract not available or failed on {image_path.name}: {e}")
        
    # Fallback: OCR engine unavailable in environment
    return {
        "text": "",
        "confidence": 0.0,
        "engine": "fallback_unavailable",
        "is_ocr_extracted": False,
        "is_visual_understanding": False,
        "note": "OCR engine not installed. Image linked by reference and page number for human expert review."
    }
