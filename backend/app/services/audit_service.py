import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.core.logging import logger

class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        actor: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        details_json = json.dumps(details or {})
        entry = AuditLog(
            action=action,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=details_json,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info(f"AUDIT [{action}] by {actor} on {resource_type} ({resource_id})")
        return entry

audit_service = AuditService()
