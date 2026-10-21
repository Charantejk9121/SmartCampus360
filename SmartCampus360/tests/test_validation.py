"""
tests/test_validation.py - Unit tests for the validators module.
These tests do NOT require a live MongoDB instance.

Run with:  python -m pytest tests/test_validation.py -v
"""

import pytest
from datetime import datetime, timezone
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validators import (
    validate_complaint,
    validate_student,
    ValidationError,
    sanitize_string,
)
import config


# ─── Complaint Validation ─────────────────────────────────────────────────────

class TestComplaintValidation:

    def _base_doc(self, **overrides):
        doc = {
            "complaint_id": "CMP1001",
            "student_id": "STU101",
            "category": "WiFi",
            "description": "WiFi is completely down in the lab room.",
            "location": "Block A",
            "priority": "High",
            "status": "Pending",
            "department": "IT Support",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "resolved_at": None,
        }
        doc.update(overrides)
        return doc

    def test_valid_complaint_passes(self):
        validate_complaint(self._base_doc())  # Must not raise

    def test_invalid_category_raises(self):
        with pytest.raises(ValidationError, match="Invalid category"):
            validate_complaint(self._base_doc(category="Unknown"), is_update=True)

    def test_invalid_priority_raises(self):
        with pytest.raises(ValidationError, match="Invalid priority"):
            validate_complaint(self._base_doc(priority="Critical"), is_update=True)

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError, match="Invalid status"):
            validate_complaint(self._base_doc(status="Done"), is_update=True)

    def test_description_too_short_raises(self):
        with pytest.raises(ValidationError, match="at least"):
            validate_complaint(self._base_doc(description="Short"))

    def test_description_minimum_length_passes(self):
        doc = self._base_doc(description="A" * config.MIN_DESCRIPTION_LENGTH)
        validate_complaint(doc)  # Must not raise

    def test_missing_student_id_raises(self):
        doc = self._base_doc()
        doc["student_id"] = ""
        with pytest.raises(ValidationError, match="required"):
            validate_complaint(doc, is_update=False)

    def test_missing_location_raises(self):
        doc = self._base_doc()
        doc["location"] = ""
        with pytest.raises(ValidationError, match="required"):
            validate_complaint(doc, is_update=False)

    def test_invalid_complaint_id_format_raises(self):
        with pytest.raises(ValidationError, match="pattern CMP"):
            validate_complaint(self._base_doc(complaint_id="ABC999"), is_update=False)

    def test_resolved_with_null_resolved_at_raises(self):
        doc = self._base_doc(status="Resolved", resolved_at=None)
        with pytest.raises(ValidationError, match="resolved_at must be set"):
            validate_complaint(doc, is_update=True)

    def test_unresolved_with_resolved_at_raises(self):
        doc = self._base_doc(status="Pending", resolved_at=datetime.now(timezone.utc))
        with pytest.raises(ValidationError, match="should be null"):
            validate_complaint(doc, is_update=True)

    def test_resolved_at_non_datetime_raises(self):
        doc = self._base_doc(status="Resolved", resolved_at="2024-01-01")
        with pytest.raises(ValidationError, match="datetime"):
            validate_complaint(doc, is_update=True)

    def test_update_validates_only_present_fields(self):
        # Only category is provided — must not fail on missing required fields
        validate_complaint({"category": "Electricity"}, is_update=True)

    def test_all_valid_categories_pass(self):
        for cat in config.CATEGORIES:
            validate_complaint({"category": cat}, is_update=True)  # No exception

    def test_all_valid_priorities_pass(self):
        for pri in config.PRIORITIES:
            validate_complaint({"priority": pri}, is_update=True)

    def test_all_valid_statuses_pass(self):
        for st in config.STATUSES:
            validate_complaint({"status": st}, is_update=True)


# ─── Student Validation ───────────────────────────────────────────────────────

class TestStudentValidation:

    def _base_student(self, **overrides):
        doc = {
            "student_id": "STU201",
            "name": "Test Student",
            "email": "test@campus.edu",
            "building": "Block A",
            "created_at": datetime.now(timezone.utc),
        }
        doc.update(overrides)
        return doc

    def test_valid_student_passes(self):
        validate_student(self._base_student())

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError, match="email"):
            validate_student(self._base_student(email="notanemail"), is_update=True)

    def test_valid_email_passes(self):
        validate_student(self._base_student(email="valid@example.co.uk"), is_update=True)

    def test_invalid_student_id_format_raises(self):
        with pytest.raises(ValidationError, match="STU"):
            validate_student(self._base_student(student_id="ABC100"), is_update=False)

    def test_empty_name_raises(self):
        doc = self._base_student()
        doc["name"] = ""
        with pytest.raises(ValidationError, match="required"):
            validate_student(doc, is_update=False)

    def test_name_too_short_raises(self):
        with pytest.raises(ValidationError, match="at least 2"):
            validate_student(self._base_student(name="A"), is_update=True)

    def test_update_only_validates_present_fields(self):
        validate_student({"name": "New Name"}, is_update=True)  # No exception

    def test_empty_building_raises(self):
        doc = self._base_student()
        doc["building"] = ""
        with pytest.raises(ValidationError, match="required"):
            validate_student(doc, is_update=False)


# ─── Sanitize Utility ─────────────────────────────────────────────────────────

class TestSanitizeString:
    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_none_returns_empty(self):
        assert sanitize_string(None) == ""

    def test_int_converts_to_string(self):
        assert sanitize_string(42) == "42"
