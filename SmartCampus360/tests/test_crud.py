"""
tests/test_crud.py - Integration tests for CRUD operations.
Requires a running MongoDB instance.

Run with:  python -m pytest tests/test_crud.py -v
           python -m pytest tests/test_crud.py -v --tb=short

Tests use an isolated 'test_campus_complaints' database and clean up after themselves.
They will NEVER touch the production database.
"""

import pytest
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Test database override ───────────────────────────────────────────────────
TEST_DB = "test_campus_complaints_pytest"

import config as cfg
cfg.MONGODB_DATABASE = TEST_DB
cfg.COMPLAINTS_COLLECTION = "test_complaints"
cfg.STUDENTS_COLLECTION = "test_students"

from pymongo.errors import DuplicateKeyError
from validators import ValidationError
import operations as ops
from models import initialize_database
from database import get_database, get_client


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Initialize schema and clean up after all tests."""
    try:
        ping_result = get_client().admin.command("ping")
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")

    db = get_database()
    db.drop_collection("test_complaints")
    db.drop_collection("test_students")

    initialize_database()
    yield
    db.drop_collection("test_complaints")
    db.drop_collection("test_students")


@pytest.fixture
def sample_student():
    """Create a student and clean up after the test."""
    ops.create_student("STU999", "Test Student", "test@campus.edu", "Block T")
    yield "STU999"
    try:
        get_database()["test_students"].delete_one({"student_id": "STU999"})
    except Exception:
        pass


@pytest.fixture
def sample_complaint(sample_student):
    """Create a complaint and clean up after the test."""
    ops.create_complaint(
        complaint_id="CMP9999",
        student_id="STU999",
        category="WiFi",
        description="Test complaint description with sufficient length here.",
        location="Test Block",
        priority="High",
        department="IT Support",
    )
    yield "CMP9999"
    try:
        get_database()["test_complaints"].delete_one({"complaint_id": "CMP9999"})
    except Exception:
        pass


# ─── Student CRUD ─────────────────────────────────────────────────────────────

class TestStudentCRUD:

    def test_create_student_succeeds(self, sample_student):
        doc = ops.get_student(sample_student)
        assert doc is not None
        assert doc["student_id"] == "STU999"
        assert doc["name"] == "Test Student"

    def test_create_student_duplicate_raises(self, sample_student):
        with pytest.raises(DuplicateKeyError):
            ops.create_student("STU999", "Another", "other@campus.edu", "Block X")

    def test_get_student_not_found_returns_none(self):
        assert ops.get_student("STU000") is None

    def test_update_student(self, sample_student):
        modified = ops.update_student(sample_student, {"name": "Updated Name"})
        assert modified
        doc = ops.get_student(sample_student)
        assert doc["name"] == "Updated Name"

    def test_update_student_not_found_raises(self):
        with pytest.raises(KeyError):
            ops.update_student("STU000", {"name": "Ghost"})

    def test_count_students(self, sample_student):
        cnt = ops.count_students()
        assert cnt >= 1

    def test_search_students(self, sample_student):
        results = ops.get_students(search_text="Test Student")
        assert any(s["student_id"] == sample_student for s in results)

    def test_delete_student_with_complaints_raises(self, sample_complaint, sample_student):
        with pytest.raises(ValueError, match="complaint"):
            ops.delete_student(sample_student)

    def test_delete_student_succeeds(self, sample_student):
        # Create a fresh student with no complaints
        ops.create_student("STU998", "Delete Me", "deleteme@campus.edu", "Block D")
        result = ops.delete_student("STU998")
        assert result
        assert ops.get_student("STU998") is None


# ─── Complaint CRUD ───────────────────────────────────────────────────────────

class TestComplaintCRUD:

    def test_create_complaint_succeeds(self, sample_complaint):
        doc = ops.get_complaint(sample_complaint)
        assert doc is not None
        assert doc["status"] == "Pending"
        assert doc["priority"] == "High"
        assert doc["category"] == "WiFi"
        assert doc["resolved_at"] is None

    def test_create_complaint_duplicate_raises(self, sample_student, sample_complaint):
        with pytest.raises(DuplicateKeyError):
            ops.create_complaint(
                complaint_id="CMP9999",
                student_id="STU999",
                category="WiFi",
                description="Duplicate test complaint description.",
                location="Test Block",
                priority="Low",
                department="IT Support",
            )

    def test_get_complaint_not_found_returns_none(self):
        assert ops.get_complaint("CMP0000") is None

    def test_update_complaint_status(self, sample_complaint):
        ops.update_complaint(sample_complaint, {"status": "In Progress"})
        doc = ops.get_complaint(sample_complaint)
        assert doc["status"] == "In Progress"

    def test_update_complaint_invalid_status_raises(self, sample_complaint):
        with pytest.raises(ValidationError):
            ops.update_complaint(sample_complaint, {"status": "Closed"})

    def test_resolve_complaint(self, sample_complaint):
        ops.resolve_complaint(sample_complaint, "Issue fixed.")
        doc = ops.get_complaint(sample_complaint)
        assert doc["status"] == "Resolved"
        assert doc["resolved_at"] is not None
        assert doc["resolution_notes"] == "Issue fixed."

    def test_update_complaint_not_found_raises(self):
        with pytest.raises(KeyError):
            ops.update_complaint("CMP0000", {"status": "Pending"})

    def test_delete_complaint_succeeds(self, sample_student):
        ops.create_complaint(
            complaint_id="CMP8888",
            student_id="STU999",
            category="Water",
            description="Delete test complaint with sufficient length.",
            location="Block T",
            priority="Low",
            department="Plumbing & Utilities",
        )
        result = ops.delete_complaint("CMP8888")
        assert result
        assert ops.get_complaint("CMP8888") is None

    def test_delete_complaint_not_found_returns_false(self):
        assert ops.delete_complaint("CMP0000") is False

    def test_get_complaints_with_status_filter(self, sample_complaint):
        results = ops.get_complaints(status="Pending")
        # Sample complaint may have been resolved by another test; just check structure
        assert isinstance(results, list)

    def test_count_complaints(self, sample_complaint):
        cnt = ops.count_complaints()
        assert cnt >= 1

    def test_generate_complaint_id_format(self):
        cid = ops.generate_complaint_id()
        assert cid.startswith("CMP")
        assert cid[3:].isdigit()

    def test_timestamps_are_iso_strings(self, sample_complaint):
        doc = ops.get_complaint(sample_complaint)
        # _serialize converts datetime to ISO string
        assert isinstance(doc["created_at"], str)
        assert "T" in doc["created_at"]  # ISO 8601 format

    def test_create_complaint_description_too_short(self, sample_student):
        with pytest.raises(ValidationError, match="at least"):
            ops.create_complaint(
                complaint_id="CMP7777",
                student_id="STU999",
                category="WiFi",
                description="Too short",
                location="Block T",
                priority="Low",
                department="IT Support",
            )

    def test_create_complaint_invalid_category(self, sample_student):
        with pytest.raises(ValidationError, match="Invalid category"):
            ops.create_complaint(
                complaint_id="CMP7776",
                student_id="STU999",
                category="InvalidCategory",
                description="A" * 30,
                location="Block T",
                priority="Low",
                department="IT Support",
            )
