import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Literal

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.review import ReviewItem

ReviewOriginValue = Literal["operational", "benchmark", "legacy_unclassified"]
BENCHMARK_ACTOR = "benchmark_evaluator"
QUERY_AUDIT_ACTIONS = ("QUERY_ANSWERED", "QUERY_ABSTAINED")
AUDIT_MATCH_WINDOW = timedelta(seconds=1)


@dataclass(frozen=True)
class ReviewOrigin:
    value: ReviewOriginValue
    evidence: str


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def classify_review_origins(
    db: Session,
    items: Iterable[ReviewItem],
) -> Dict[str, ReviewOrigin]:
    review_items = list(items)
    origins: Dict[str, ReviewOrigin] = {}
    legacy_items = []

    for item in review_items:
        if item.origin == "benchmark":
            origins[item.id] = ReviewOrigin(
                "benchmark", "Origin recorded by the evaluation workflow."
            )
        elif item.origin == "operational":
            origins[item.id] = ReviewOrigin(
                "operational", "Origin recorded when the review item was created."
            )
        else:
            legacy_items.append(item)

    safety_items = [
        item for item in legacy_items
        if item.item_type == "safety_critical_query"
    ]
    safety_audits = []
    if safety_items:
        safety_audits = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "SAFETY_ESCALATION",
                AuditLog.resource_type == "query",
                AuditLog.resource_id.in_([item.id for item in safety_items]),
            )
            .all()
        )

    safety_audits_by_review_id: Dict[str, list[AuditLog]] = {}
    for audit in safety_audits:
        safety_audits_by_review_id.setdefault(audit.resource_id, []).append(audit)

    for item in safety_items:
        matches = safety_audits_by_review_id.get(item.id, [])
        if len(matches) == 1:
            audit = matches[0]
            value: ReviewOriginValue = (
                "benchmark" if audit.actor == BENCHMARK_ACTOR else "operational"
            )
            origins[item.id] = ReviewOrigin(
                value, f"Linked safety escalation audit event {audit.id}."
            )
        else:
            origins[item.id] = ReviewOrigin(
                "legacy_unclassified",
                "No unique linked safety escalation audit event; retained in the operational queue.",
            )

    conflict_items = [
        item for item in legacy_items
        if item.item_type == "document_conflict"
    ]
    if conflict_items:
        oldest = min(_utc_naive(item.created_at) for item in conflict_items)
        newest = max(_utc_naive(item.created_at) for item in conflict_items)
        query_audits = (
            db.query(AuditLog)
            .filter(
                AuditLog.action.in_(QUERY_AUDIT_ACTIONS),
                AuditLog.resource_type == "query",
                AuditLog.timestamp >= oldest - AUDIT_MATCH_WINDOW,
                AuditLog.timestamp <= newest + AUDIT_MATCH_WINDOW,
            )
            .all()
        )

        audit_questions = []
        for audit in query_audits:
            details = json.loads(audit.details_json or "{}")
            question = details.get("question")
            if isinstance(question, str) and question:
                audit_questions.append((audit, question, _utc_naive(audit.timestamp)))

        candidate_matches = []
        for item in conflict_items:
            details = json.loads(item.details_json or "{}")
            question = details.get("question")
            if not isinstance(question, str) or not question:
                continue
            created_at = _utc_naive(item.created_at)
            for audit, audit_question, audit_time in audit_questions:
                delta = audit_time - created_at
                if (
                    question == audit_question
                    and timedelta(0) <= delta <= AUDIT_MATCH_WINDOW
                ):
                    candidate_matches.append(
                        (delta, item.id, audit.id, item, audit)
                    )

        matched_items = set()
        matched_audits = set()
        for _, _, _, item, audit in sorted(candidate_matches):
            if item.id in matched_items or audit.id in matched_audits:
                continue
            matched_items.add(item.id)
            matched_audits.add(audit.id)
            value = (
                "benchmark" if audit.actor == BENCHMARK_ACTOR else "operational"
            )
            origins[item.id] = ReviewOrigin(
                value,
                f"Matched query audit event {audit.id} by exact question and timestamp within one second.",
            )

    for item in legacy_items:
        if item.id not in origins:
            origins[item.id] = ReviewOrigin(
                "legacy_unclassified",
                "No reliable audit-event match; retained in the operational queue.",
            )

    return origins
