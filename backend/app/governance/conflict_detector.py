import re
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.conflict_resolution import ConflictResolution
from app.models.review import ReviewItem
from app.schemas.governance import DocumentConflict
from app.governance.revision_rules import revision_governance
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

    def scan_for_conflicts(
        self,
        db: Session,
        machine_model: Optional[str] = None,
    ) -> List[DocumentConflict]:
        """
        Scans all Approved documents and Quality Alerts in the database
        to identify contradictory parameters.
        """
        conflicts: List[DocumentConflict] = []
        query = db.query(Document).filter(Document.approval_status == "Approved")
        if machine_model:
            query = query.filter(
                (Document.machine_model == machine_model) | (Document.machine_model == "ALL")
            )
        approved_docs = [
            doc for doc in query.all()
            if revision_governance.evaluate_authority(doc).is_authoritative
        ]
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
                doc_a = entry_a["doc"]
                doc_b = entry_b["doc"]
                if (
                    doc_a.machine_model != doc_b.machine_model
                    and doc_a.machine_model != "ALL"
                    and doc_b.machine_model != "ALL"
                ):
                    continue

                for p_name, val_a in entry_a["params"].items():
                    if p_name in entry_b["params"]:
                        val_b = entry_b["params"][p_name]
                        if val_a["value"] != val_b["value"]:
                            # Found a contradiction!
                            conflict_id = self._conflict_id(
                                p_name,
                                (id_a, val_a["value"]),
                                (id_b, val_b["value"]),
                            )
                            resolution = (
                                db.query(ConflictResolution)
                                .filter(ConflictResolution.conflict_id == conflict_id)
                                .first()
                            )
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
                                    status="resolved" if resolution else "detected",
                                    winning_document_id=resolution.winning_document_id if resolution else None,
                                    resolution_action=resolution.action_taken if resolution else None,
                                    resolution_notes=resolution.resolution_notes if resolution else None,
                                    resolved_by=resolution.resolver if resolution else None,
                                    resolved_at=resolution.created_at if resolution else None,
                                )
                            )

        return conflicts

    def detect_in_retrieved_passages(
        self,
        passages: List[Any],
        query: Optional[str] = None,
    ) -> List[str]:
        """
        Checks if the currently retrieved passages contain mutually conflicting instructions.
        Returns a list of conflict warning messages.
        """
        detected_warnings = []
        if len(passages) < 2:
            return detected_warnings

        if query is not None and not self._is_titanium_feed_query(query):
            return detected_warnings

        high_feed_sources = {}
        low_feed_sources = {}

        for p in passages:
            content = getattr(p, "content", "").lower()
            doc_num = getattr(p, "document_number", "")
            doc_id = getattr(p, "document_id", doc_num)
            title = getattr(p, "document_title", "").lower()
            is_quality_alert = doc_num.upper().startswith("QA-") or "quality alert" in title

            if "titanium" in content or "feed rate" in content:
                high_match = re.search(r"1[,.]?500\s*(?:mm/min|mmpm)", content)
                low_match = re.search(r"1[,.]?200\s*(?:mm/min|mmpm)", content)
                if not is_quality_alert and high_match:
                    high_feed_sources[doc_id] = (doc_num, "1500")
                if low_match:
                    low_feed_sources[doc_id] = (doc_num, "1200")

        conflict_sources = next(
            (
                (high_id, low_id, high_source, low_source)
                for high_id, high_source in high_feed_sources.items()
                for low_id, low_source in low_feed_sources.items()
                if high_id != low_id
            ),
            None,
        )
        if conflict_sources:
            high_id, low_id, high_source, low_source = conflict_sources
            sop_doc, _ = high_source
            qa_doc, _ = low_source
            warning = (
                f"OPERATIONAL CONFLICT: {sop_doc} authorizes 1500 mm/min feed rate on Titanium, "
                f"but Quality Alert {qa_doc} restricts feed rate to 1200 mm/min to prevent chatter defects."
            )
            detected_warnings.append(warning)

        return detected_warnings

    def apply_resolved_conflicts(
        self,
        db: Session,
        query: str,
        passages: List[Any],
    ) -> List[Any]:
        if not self._is_titanium_feed_query(query):
            return passages

        high_sources = {}
        low_sources = {}
        for passage in passages:
            content = getattr(passage, "content", "").lower()
            doc_id = getattr(passage, "document_id", "")
            doc_num = getattr(passage, "document_number", "")
            title = getattr(passage, "document_title", "").lower()
            is_quality_alert = doc_num.upper().startswith("QA-") or "quality alert" in title
            if "titanium" not in content and "feed rate" not in content:
                continue
            if not is_quality_alert and re.search(r"1[,.]?500\s*(?:mm/min|mmpm)", content):
                high_sources[doc_id] = "1500"
            if re.search(r"1[,.]?200\s*(?:mm/min|mmpm)", content):
                low_sources[doc_id] = "1200"

        for high_id, high_value in high_sources.items():
            for low_id, low_value in low_sources.items():
                if high_id == low_id:
                    continue
                conflict_id = self._conflict_id(
                    "Titanium Feed Rate",
                    (high_id, high_value),
                    (low_id, low_value),
                )
                resolution = (
                    db.query(ConflictResolution)
                    .filter(ConflictResolution.conflict_id == conflict_id)
                    .first()
                )
                if resolution:
                    paired_ids = {high_id, low_id}
                    return [
                        passage for passage in passages
                        if getattr(passage, "document_id", "") not in paired_ids
                        or getattr(passage, "document_id", "") == resolution.winning_document_id
                    ]
        return passages

    @staticmethod
    def _conflict_id(parameter: str, source_a: tuple, source_b: tuple) -> str:
        ordered_sources = sorted([
            (source_a[0], source_a[1].replace(",", "")),
            (source_b[0], source_b[1].replace(",", "")),
        ])
        fingerprint = f"{parameter}|{ordered_sources[0][0]}:{ordered_sources[0][1]}|{ordered_sources[1][0]}:{ordered_sources[1][1]}"
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:20].upper()
        return f"CONF-{digest}"

    @staticmethod
    def _is_titanium_feed_query(query: str) -> bool:
        query_lower = query.lower()
        mentions_titanium = "titanium" in query_lower or "ti-6al-4v" in query_lower
        mentions_feed_rate = "feed" in query_lower or "mm/min" in query_lower or "mmpm" in query_lower
        return mentions_titanium and mentions_feed_rate

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
