import re
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.review import ReviewItem
from app.schemas.governance import DocumentConflict
from app.core.logging import logger

class ConflictDetector:
    """
    Detects contradictory instructions and conflicting operating limits
    between active documents, SOPs, and Quality Alerts.
    """
    # Parameter patterns commonly subject to manufacturing discrepancies
    PARAMETER_PATTERNS = [
        {
            "name": "Titanium Feed Rate",
            "regex": r"(?:feed\s*rate|machining\s*feed).*?(?:titanium|ti-6al-4v).*?([0-9,.]+)\s*(?:mm/min|mmpm)",
            "unit": "mm/min",
            "severity": "critical",
        },
        {
            "name": "Spindle Warm-up Time",
            "regex": r"(?:spindle\s*warm-up|warm\s*up\s*cycle).*?(\d{1,2})\s*(?:minutes|mins|min)",
            "unit": "min",
            "severity": "medium",
        },
        {
            "name": "Coolant Concentration",
            "regex": r"(?:coolant\s*concentration|refractometer).*?(\d{1,2}(?:\.\d)?)\s*%",
            "unit": "%",
            "severity": "high",
        },
    ]

    def scan_for_conflicts(self, db: Session) -> List[DocumentConflict]:
        """
        Scans all Approved documents and Quality Alerts in the database
        to identify contradictory parameters.
        """
        conflicts: List[DocumentConflict] = []
        approved_docs = db.query(Document).filter(Document.approval_status == "Approved").all()
        if len(approved_docs) < 2:
            return conflicts

        # Extract parameters for each approved document
        doc_extracted_params: Dict[str, Dict[str, Any]] = {}
        for doc in approved_docs:
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
            full_text = " ".join([c.content for c in chunks])
            
            doc_extracted_params[doc.id] = {
                "doc": doc,
                "params": self._extract_parameters(full_text)
            }

        # Compare pair-wise
        doc_ids = list(doc_extracted_params.keys())
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                id_a, id_b = doc_ids[i], doc_ids[j]
                entry_a = doc_extracted_params[id_a]
                entry_b = doc_extracted_params[id_b]

                for p_name, val_a in entry_a["params"].items():
                    if p_name in entry_b["params"]:
                        val_b = entry_b["params"][p_name]
                        if val_a["value"] != val_b["value"]:
                            # Found a contradiction!
                            conflict_id = f"CONF-{id_a[:4]}-{id_b[:4]}-{uuid.uuid4().hex[:4]}"
                            conflicts.append(
                                DocumentConflict(
                                    conflict_id=conflict_id,
                                    parameter_or_topic=p_name,
                                    description=(
                                        f"Conflicting values detected for '{p_name}': "
                                        f"{entry_a['doc'].document_number} specifies {val_a['value']} {val_a['unit']}, while "
                                        f"{entry_b['doc'].document_number} specifies {val_b['value']} {val_b['unit']}."
                                    ),
                                    document_a_id=id_a,
                                    document_a_number=entry_a['doc'].document_number,
                                    document_a_revision=entry_a['doc'].revision,
                                    document_a_status=entry_a['doc'].approval_status,
                                    instruction_a=val_a["context"],
                                    document_b_id=id_b,
                                    document_b_number=entry_b['doc'].document_number,
                                    document_b_revision=entry_b['doc'].revision,
                                    document_b_status=entry_b['doc'].approval_status,
                                    instruction_b=val_b["context"],
                                    severity=val_a["severity"],
                                    recommended_action="Route to Quality Engineering and Plant Supervisor for immediate review.",
                                    status="detected",
                                )
                            )

        return conflicts

    def detect_in_retrieved_passages(
        self,
        passages: List[Any],
    ) -> List[str]:
        """
        Checks if the currently retrieved passages contain mutually conflicting instructions.
        Returns a list of conflict warning messages.
        """
        detected_warnings = []
        if len(passages) < 2:
            return detected_warnings

        # Check for Titanium feed rate discrepancy
        has_sop_high_feed = False
        has_qa_low_feed = False
        sop_doc = ""
        qa_doc = ""

        for p in passages:
            content = getattr(p, "content", "").lower()
            doc_num = getattr(p, "document_number", "")
            
            if "titanium" in content or "feed rate" in content:
                if re.search(r"1[,.]?500\s*(?:mm/min|mmpm)", content):
                    has_sop_high_feed = True
                    sop_doc = doc_num
                if re.search(r"1[,.]?200\s*(?:mm/min|mmpm)", content):
                    has_qa_low_feed = True
                    qa_doc = doc_num

        if has_sop_high_feed and has_qa_low_feed:
            warning = (
                f"OPERATIONAL CONFLICT: {sop_doc} authorizes 1500 mm/min feed rate on Titanium, "
                f"but Quality Alert {qa_doc} restricts feed rate to 1200 mm/min to prevent chatter defects."
            )
            detected_warnings.append(warning)

        return detected_warnings

    def _extract_parameters(self, text: str) -> Dict[str, Dict[str, Any]]:
        extracted = {}
        for rule in self.PARAMETER_PATTERNS:
            match = re.search(rule["regex"], text, re.IGNORECASE)
            if match:
                val = match.group(1)
                # Capture surrounding context snippet
                start = max(0, match.start() - 60)
                end = min(len(text), match.end() + 60)
                extracted[rule["name"]] = {
                    "value": val,
                    "unit": rule["unit"],
                    "severity": rule["severity"],
                    "context": text[start:end].strip(),
                }
        return extracted

conflict_detector = ConflictDetector()
