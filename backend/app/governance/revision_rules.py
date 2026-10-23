from datetime import datetime, timezone
from typing import Tuple, Optional
from app.models.document import Document
from app.schemas.governance import RevisionCheckResult

class RevisionGovernanceEngine:
    """
    Enforces deterministic shop-floor revision authority rules.
    
    GOVERNANCE CONSTRAINTS:
    1. Only documents with explicit status 'Approved' are authoritative.
    2. Effective date must be <= current date.
    3. Expiry date (if set) must be >= current date.
    4. Superseded or Withdrawn documents are NEVER authoritative.
    5. Upload timestamp or creation date NEVER confers authority.
    6. LLMs are prohibited from deciding revision validity.
    """
    AUTHORITATIVE_STATUSES = {"Approved"}
    NON_AUTHORITATIVE_STATUSES = {
        "Draft",
        "Pending Review",
        "Superseded",
        "Withdrawn",
        "Expired",
        "Not Yet Effective",
    }

    def evaluate_authority(self, doc: Document, now: Optional[datetime] = None) -> RevisionCheckResult:
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure tz-awareness
        if doc.effective_date and doc.effective_date.tzinfo is None:
            effective_dt = doc.effective_date.replace(tzinfo=timezone.utc)
        else:
            effective_dt = doc.effective_date

        if doc.expiry_date and doc.expiry_date.tzinfo is None:
            expiry_dt = doc.expiry_date.replace(tzinfo=timezone.utc)
        else:
            expiry_dt = doc.expiry_date

        # Rule 1: Check explicit approval status
        if doc.approval_status not in self.AUTHORITATIVE_STATUSES:
            return RevisionCheckResult(
                is_authoritative=False,
                status=doc.approval_status,
                effective_date=doc.effective_date,
                expiry_date=doc.expiry_date,
                superseded_by=doc.superseded_by_id,
                reason=f"Document status is '{doc.approval_status}'. Explicit approval is required for operational authority."
            )

        # Rule 2: Check superseded link
        if doc.superseded_by_id:
            return RevisionCheckResult(
                is_authoritative=False,
                status="Superseded",
                effective_date=doc.effective_date,
                expiry_date=doc.expiry_date,
                superseded_by=doc.superseded_by_id,
                reason=f"Document is superseded by Document ID {doc.superseded_by_id}."
            )

        # Rule 3: Check effective date
        if effective_dt and effective_dt > now:
            return RevisionCheckResult(
                is_authoritative=False,
                status="Not Yet Effective",
                effective_date=doc.effective_date,
                expiry_date=doc.expiry_date,
                superseded_by=None,
                reason=f"Document effective date ({doc.effective_date.strftime('%Y-%m-%d')}) has not arrived yet."
            )

        # Rule 4: Check expiry date
        if expiry_dt and expiry_dt < now:
            return RevisionCheckResult(
                is_authoritative=False,
                status="Expired",
                effective_date=doc.effective_date,
                expiry_date=doc.expiry_date,
                superseded_by=None,
                reason=f"Document expired on {doc.expiry_date.strftime('%Y-%m-%d')}."
            )

        # Passed all rules
        return RevisionCheckResult(
            is_authoritative=True,
            status="Approved",
            effective_date=doc.effective_date,
            expiry_date=doc.expiry_date,
            superseded_by=None,
            reason="Document is currently approved and within its active effective date window."
        )

revision_governance = RevisionGovernanceEngine()
