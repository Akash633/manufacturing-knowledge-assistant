import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from fastapi import HTTPException

from app.api.routes.review import get_review_queue, take_review_action
from app.core.auth import AuthenticatedUser
from app.db.migrations import ensure_review_origin_column
from app.models.audit import AuditLog
from app.models.review import ReviewItem
from app.schemas.review import ReviewActionRequest
from app.services.review_origin import classify_review_origins


def _review_item(db, item_type, question, created_at, origin=None):
    item = ReviewItem(
        id=str(uuid.uuid4()),
        item_type=item_type,
        status="pending",
        origin=origin,
        priority="high",
        title="Review required",
        summary="Review test record.",
        details_json=json.dumps({"question": question}),
        created_at=created_at,
    )
    db.add(item)
    db.flush()
    return item


def _query_audit(db, question, timestamp, actor):
    audit = AuditLog(
        id=str(uuid.uuid4()),
        action="QUERY_ANSWERED",
        actor=actor,
        resource_type="query",
        details_json=json.dumps({"question": question}),
        timestamp=timestamp,
    )
    db.add(audit)
    db.flush()
    return audit


def test_review_queue_excludes_only_audit_linked_benchmark_items(test_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    benchmark_safety = _review_item(
        test_db, "safety_critical_query", "benchmark safety query", now
    )
    operational_safety = _review_item(
        test_db, "safety_critical_query", "operator safety query", now
    )
    benchmark_conflict = _review_item(
        test_db, "document_conflict", "benchmark conflict query", now
    )
    operational_conflict = _review_item(
        test_db, "document_conflict", "operator conflict query", now
    )
    unmatched_legacy = _review_item(
        test_db, "document_conflict", "unmatched legacy query", now
    )

    test_db.add_all(
        [
            AuditLog(
                action="SAFETY_ESCALATION",
                actor="benchmark_evaluator",
                resource_type="query",
                resource_id=benchmark_safety.id,
                details_json="{}",
                timestamp=now,
            ),
            AuditLog(
                action="SAFETY_ESCALATION",
                actor="operator",
                resource_type="query",
                resource_id=operational_safety.id,
                details_json="{}",
                timestamp=now,
            ),
        ]
    )
    benchmark_audit = _query_audit(
        test_db, "benchmark conflict query", now + timedelta(milliseconds=20),
        "benchmark_evaluator",
    )
    operational_audit = _query_audit(
        test_db, "operator conflict query", now + timedelta(milliseconds=30),
        "operator",
    )
    test_db.commit()

    # Represent pre-migration records whose origin column was added as NULL.
    for item in (
        benchmark_safety,
        operational_safety,
        benchmark_conflict,
        operational_conflict,
        unmatched_legacy,
    ):
        test_db.execute(
            text("UPDATE review_items SET origin = NULL WHERE id = :id"),
            {"id": item.id},
        )
    test_db.commit()

    pending = get_review_queue(
        status="pending",
        item_type=None,
        origin="operational",
        db=test_db,
    )
    assert {item.id for item in pending} == {
        operational_safety.id,
        operational_conflict.id,
        unmatched_legacy.id,
    }
    assert {item.origin for item in pending} == {
        "operational",
        "legacy_unclassified",
    }

    benchmark_history = get_review_queue(
        status="pending",
        item_type=None,
        origin="benchmark",
        db=test_db,
    )
    assert {item.id for item in benchmark_history} == {
        benchmark_safety.id,
        benchmark_conflict.id,
    }
    assert benchmark_history[0].origin_evidence
    assert any(
        benchmark_audit.id in item.origin_evidence for item in benchmark_history
    )
    assert operational_audit.id not in {
        item.origin_evidence for item in benchmark_history
    }

    all_history = get_review_queue(
        status="pending",
        item_type=None,
        origin="all",
        db=test_db,
    )
    assert len(all_history) == 5


def test_repeated_conflict_audit_events_are_matched_one_to_one(test_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    items = [
        _review_item(test_db, "document_conflict", "same benchmark query", now),
        _review_item(
            test_db,
            "document_conflict",
            "same benchmark query",
            now + timedelta(milliseconds=100),
        ),
    ]
    audits = [
        _query_audit(
            test_db,
            "same benchmark query",
            now + timedelta(milliseconds=120),
            "benchmark_evaluator",
        ),
        _query_audit(
            test_db,
            "same benchmark query",
            now + timedelta(milliseconds=200),
            "benchmark_evaluator",
        ),
    ]
    test_db.commit()
    for item in items:
        test_db.execute(
            text("UPDATE review_items SET origin = NULL WHERE id = :id"),
            {"id": item.id},
        )
    test_db.commit()

    origins = classify_review_origins(test_db, items)
    assert all(origins[item.id].value == "benchmark" for item in items)
    assert len({origins[item.id].evidence for item in items}) == 2
    assert {
        audit.id for audit in audits
    } == {
        origins[item.id].evidence.split("Matched query audit event ", 1)[1].split(" ", 1)[0].rstrip(".")
        for item in items
    }


def test_benchmark_history_cannot_be_actioned_as_operational_review(test_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    item = _review_item(test_db, "safety_critical_query", "benchmark safety query", now)
    test_db.add(
        AuditLog(
            action="SAFETY_ESCALATION",
            actor="benchmark_evaluator",
            resource_type="query",
            resource_id=item.id,
            details_json="{}",
            timestamp=now,
        )
    )
    test_db.commit()
    test_db.execute(
        text("UPDATE review_items SET origin = NULL WHERE id = :id"),
        {"id": item.id},
    )
    test_db.commit()

    try:
        take_review_action(
            item.id,
            ReviewActionRequest(action="approved", expert_notes="Not an operational task."),
            db=test_db,
            user=AuthenticatedUser(subject="reviewer", roles=frozenset({"expert_reviewer"})),
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Benchmark-generated history must not accept review actions.")

    test_db.refresh(item)
    assert item.status == "pending"


def test_review_origin_migration_adds_nullable_column_without_changing_rows():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE review_items ("
                    "id VARCHAR(36) PRIMARY KEY, title VARCHAR(255) NOT NULL)"
                )
            )
            connection.execute(
                text("INSERT INTO review_items (id, title) VALUES ('legacy-1', 'Keep me')")
            )

        ensure_review_origin_column(engine)

        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT id, title, origin FROM review_items WHERE id = 'legacy-1'")
            ).one()
        assert tuple(row) == ("legacy-1", "Keep me", None)
    finally:
        engine.dispose()
