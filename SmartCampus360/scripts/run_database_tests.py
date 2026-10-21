"""
scripts/run_database_tests.py
Quick integration smoke-test that exercises the live database.
Requires a running MongoDB instance.

Usage:
    python scripts/run_database_tests.py
    python scripts/run_database_tests.py --database test_campus_complaints
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from database import ping, get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results = []


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, label))
    logger.info("  %s  %s%s", status, label, f" — {detail}" if detail else "")


def run_tests(db_name: str):
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError, WriteError

    client = get_client()
    db = client[db_name]

    # Ensure fresh test collections
    for col in ["test_complaints", "test_students"]:
        db.drop_collection(col)

    from models import initialize_database
    import config as cfg

    # Override collection names temporarily for tests
    original_c = cfg.COMPLAINTS_COLLECTION
    original_s = cfg.STUDENTS_COLLECTION
    cfg.COMPLAINTS_COLLECTION = "test_complaints"
    cfg.STUDENTS_COLLECTION = "test_students"
    original_db = cfg.MONGODB_DATABASE
    cfg.MONGODB_DATABASE = db_name

    try:
        # Reinitialize client reference to use test db
        from database import _ensure_db_initialized
        init_result = initialize_database()

        logger.info("\n=== Schema Initialization ===")
        check("Collections created", "test_complaints" in db.list_collection_names())
        check("Indexes created", "idx_complaint_id_unique" in
              db["test_complaints"].index_information())

        logger.info("\n=== CRUD Operations ===")
        import operations as ops

        # Valid insert
        try:
            ops.create_complaint(
                complaint_id="CMP9001",
                student_id="STU101",
                category="WiFi",
                description="Test complaint description minimum length ok",
                location="Test Block",
                priority="High",
                department="IT Support",
            )
            check("insert_one valid complaint", True)
        except Exception as exc:
            check("insert_one valid complaint", False, str(exc))

        # Duplicate key
        try:
            ops.create_complaint(
                complaint_id="CMP9001",
                student_id="STU101",
                category="WiFi",
                description="Test complaint description duplicate",
                location="Test Block",
                priority="High",
                department="IT Support",
            )
            check("Duplicate key rejected", False, "No exception raised")
        except DuplicateKeyError:
            check("Duplicate key rejected", True)

        # find_one
        doc = ops.get_complaint("CMP9001")
        check("find_one complaint", doc is not None)
        check("Status defaults to Pending", doc and doc.get("status") == "Pending")

        # update_one
        try:
            ops.update_complaint("CMP9001", {"status": "In Progress"})
            updated = ops.get_complaint("CMP9001")
            check("update_one status", updated and updated.get("status") == "In Progress")
        except Exception as exc:
            check("update_one status", False, str(exc))

        # Resolve
        try:
            ops.resolve_complaint("CMP9001", "Resolved in test.")
            resolved = ops.get_complaint("CMP9001")
            check("resolve sets Resolved status", resolved and resolved.get("status") == "Resolved")
            check("resolve sets resolved_at", resolved and resolved.get("resolved_at") is not None)
        except Exception as exc:
            check("resolve_complaint", False, str(exc))

        # count_documents
        cnt = db["test_complaints"].count_documents({})
        check("count_documents > 0", cnt > 0, f"count={cnt}")

        # Invalid category
        from validators import validate_complaint, ValidationError
        try:
            validate_complaint({"category": "InvalidCat"}, is_update=True)
            check("Invalid category rejected", False, "No exception")
        except ValidationError:
            check("Invalid category rejected", True)

        # Invalid priority
        try:
            validate_complaint({"priority": "Ultra"}, is_update=True)
            check("Invalid priority rejected", False, "No exception")
        except ValidationError:
            check("Invalid priority rejected", True)

        # Missing required fields
        from validators import validate_complaint as vc
        try:
            vc({"category": "WiFi"}, is_update=False)
            check("Missing required fields caught", False, "No exception")
        except ValidationError:
            check("Missing required fields caught", True)

        # delete_one
        try:
            del_result = ops.delete_complaint("CMP9001")
            check("delete_one complaint", del_result)
            check("find after delete returns None", ops.get_complaint("CMP9001") is None)
        except Exception as exc:
            check("delete_one complaint", False, str(exc))

        logger.info("\n=== Student Operations ===")
        try:
            ops.create_student("STU901", "Test Student", "test@campus.edu", "Block T")
            check("insert_one valid student", True)
        except Exception as exc:
            check("insert_one valid student", False, str(exc))

        try:
            ops.create_student("STU901", "Dup Student", "dup@campus.edu", "Block T")
            check("Duplicate student ID rejected", False)
        except DuplicateKeyError:
            check("Duplicate student ID rejected", True)

        from validators import validate_student, ValidationError as VE
        try:
            validate_student({"email": "bademail"})
            check("Invalid email rejected", False)
        except VE:
            check("Invalid email rejected", True)

        logger.info("\n=== Aggregation Pipelines ===")
        # Insert some data for aggregation tests
        db["test_complaints"].insert_many([
            {
                "complaint_id": f"CMP{9010+i}",
                "student_id": "STU901",
                "category": cat,
                "description": "Aggregation test complaint with sufficient length.",
                "location": "Test Block",
                "priority": "High",
                "status": status,
                "department": "IT Support",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "resolved_at": datetime.now(timezone.utc) if status == "Resolved" else None,
                "resolution_notes": "Done" if status == "Resolved" else None,
                "additional_details": None,
            }
            for i, (cat, status) in enumerate([
                ("WiFi", "Pending"),
                ("WiFi", "Resolved"),
                ("Electricity", "In Progress"),
                ("Water", "Resolved"),
            ])
        ])

        import analytics as an
        by_cat = an.complaints_by_category()
        check("Pipeline 1: by_category returns data", len(by_cat) > 0, f"{len(by_cat)} rows")

        by_status = an.complaints_by_status()
        check("Pipeline 2: by_status returns all statuses", len(by_status) == 3)

        by_priority = an.complaints_by_priority()
        check("Pipeline 3: by_priority returns data", len(by_priority) > 0)

        rv = an.resolved_vs_unresolved()
        check("Pipeline 10: resolved>0", rv.get("resolved", 0) > 0)
        check("Resolution rate in [0,100]", 0 <= rv.get("resolution_rate", 0) <= 100)

        dept_data = an.department_workload()
        check("Pipeline 6: department_workload", len(dept_data) > 0)

        avg_rt = an.avg_resolution_time_by_category()
        check("Pipeline 5: avg_resolution_time valid", all(r["avg_hours"] > 0 for r in avg_rt))

    finally:
        # Cleanup
        for col in ["test_complaints", "test_students"]:
            db.drop_collection(col)
        cfg.COMPLAINTS_COLLECTION = original_c
        cfg.STUDENTS_COLLECTION = original_s
        cfg.MONGODB_DATABASE = original_db

    # ── Summary ────────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 55)
    logger.info("TEST RESULTS")
    logger.info("=" * 55)
    passed = sum(1 for s, _ in results if "PASS" in s)
    failed = sum(1 for s, _ in results if "FAIL" in s)
    for status, label in results:
        logger.info("  %s  %s", status, label)
    logger.info("=" * 55)
    logger.info("  Passed: %d / %d", passed, len(results))
    if failed:
        logger.info("  Failed: %d", failed)
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Run SmartCampus 360 integration tests.")
    parser.add_argument("--database", default="test_campus_complaints",
                        help="Test database name (default: test_campus_complaints)")
    args = parser.parse_args()

    logger.info("Checking connection…")
    status = ping()
    if not status["connected"]:
        logger.error("Cannot connect to MongoDB: %s", status["error"])
        sys.exit(1)

    logger.info("Running tests against database: %s", args.database)
    success = run_tests(args.database)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
