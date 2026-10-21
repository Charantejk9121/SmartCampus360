"""
operations.py - Centralised CRUD operations for SmartCampus 360.

All database reads and writes go through this module.
Business-rule validation is applied before any write reaches MongoDB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, WriteError, OperationFailure

import config
from database import get_complaints_collection, get_students_collection
from validators import ValidationError, validate_complaint, validate_student

logger = logging.getLogger(__name__)


# ─── Utility ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def _serialize(doc: Optional[dict]) -> Optional[dict]:
    """Convert ObjectId and datetime fields to JSON-safe types for display."""
    if doc is None:
        return None
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLAINT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_complaint(
    complaint_id: str,
    student_id: str,
    category: str,
    description: str,
    location: str,
    priority: str,
    department: str,
    additional_details: Optional[str] = None,
) -> dict:
    """
    Insert a new complaint document.
    Returns the inserted document (serialized).
    Raises ValidationError or DuplicateKeyError on failure.
    """
    now = _now()
    doc = {
        "complaint_id": complaint_id.strip(),
        "student_id": student_id.strip(),
        "category": category,
        "description": description.strip(),
        "location": location.strip(),
        "priority": priority,
        "status": "Pending",          # always starts as Pending
        "department": department.strip(),
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
        "resolution_notes": None,
        "additional_details": additional_details.strip() if additional_details else None,
    }

    # Python-layer validation
    validate_complaint(doc)

    col = get_complaints_collection()
    try:
        result = col.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info("Complaint '%s' created (OID=%s).", complaint_id, result.inserted_id)
        return _serialize(doc)
    except DuplicateKeyError:
        raise DuplicateKeyError(
            f"Complaint ID '{complaint_id}' already exists. Use a unique ID.", None, None
        )
    except WriteError as exc:
        logger.error("MongoDB WriteError inserting complaint: %s", exc)
        raise


def get_complaint(complaint_id: str) -> Optional[dict]:
    """Return a single complaint document by complaint_id, or None."""
    doc = get_complaints_collection().find_one({"complaint_id": complaint_id})
    return _serialize(doc)


def get_complaints(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    department: Optional[str] = None,
    student_id: Optional[str] = None,
    search_text: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_field: str = "created_at",
    sort_order: int = DESCENDING,
    limit: int = config.DEFAULT_PAGE_SIZE,
    skip: int = 0,
) -> list[dict]:
    """
    Return complaints matching the given filters.
    All parameters are optional; omitting them returns all complaints.
    """
    query: dict[str, Any] = {}

    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if priority:
        query["priority"] = priority
    if department:
        query["department"] = department
    if student_id:
        query["student_id"] = student_id

    if search_text:
        pattern = {"$regex": search_text, "$options": "i"}
        query["$or"] = [
            {"complaint_id": pattern},
            {"student_id": pattern},
            {"description": pattern},
            {"location": pattern},
        ]

    if date_from or date_to:
        date_filter: dict = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        query["created_at"] = date_filter

    cursor = (
        get_complaints_collection()
        .find(query)
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )
    return [_serialize(doc) for doc in cursor]


def count_complaints(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    department: Optional[str] = None,
    student_id: Optional[str] = None,
    search_text: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> int:
    """Return the count of complaints matching the given filters."""
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if priority:
        query["priority"] = priority
    if department:
        query["department"] = department
    if student_id:
        query["student_id"] = student_id
    if search_text:
        pattern = {"$regex": search_text, "$options": "i"}
        query["$or"] = [
            {"complaint_id": pattern},
            {"student_id": pattern},
            {"description": pattern},
            {"location": pattern},
        ]
    if date_from or date_to:
        date_filter: dict = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        query["created_at"] = date_filter

    return get_complaints_collection().count_documents(query)


def update_complaint(complaint_id: str, updates: dict[str, Any]) -> bool:
    """
    Update one or more fields on an existing complaint.
    Always refreshes updated_at.
    Returns True if a document was modified.
    Raises ValidationError on invalid field values.
    """
    if not updates:
        return False

    # Validate only the fields being updated
    validate_complaint(updates, is_update=True)

    updates["updated_at"] = _now()

    # Automatically manage resolved_at
    if updates.get("status") == "Resolved":
        updates.setdefault("resolved_at", _now())
    elif "status" in updates and updates["status"] != "Resolved":
        updates["resolved_at"] = None

    result = get_complaints_collection().update_one(
        {"complaint_id": complaint_id},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise KeyError(f"Complaint '{complaint_id}' not found.")
    logger.info("Complaint '%s' updated: %s", complaint_id, list(updates.keys()))
    return result.modified_count > 0


def resolve_complaint(
    complaint_id: str, resolution_notes: Optional[str] = None
) -> bool:
    """Convenience wrapper: set status to Resolved with timestamp."""
    return update_complaint(
        complaint_id,
        {
            "status": "Resolved",
            "resolved_at": _now(),
            "resolution_notes": resolution_notes,
        },
    )


def delete_complaint(complaint_id: str) -> bool:
    """
    Permanently delete a complaint.
    Returns True if deleted, False if not found.
    This is a destructive action — callers must confirm before calling.
    """
    result = get_complaints_collection().delete_one({"complaint_id": complaint_id})
    if result.deleted_count:
        logger.warning("Complaint '%s' deleted.", complaint_id)
    return result.deleted_count > 0


def generate_complaint_id() -> str:
    """
    Generate the next complaint ID by finding the highest existing numeric suffix.
    Falls back to CMP1001 when the collection is empty.
    """
    col = get_complaints_collection()
    # Find all CMP* ids and compute the max numeric part
    docs = col.find(
        {"complaint_id": {"$regex": r"^CMP\d+$"}},
        {"complaint_id": 1, "_id": 0},
    ).sort("complaint_id", DESCENDING).limit(1)
    docs = list(docs)
    if not docs:
        return "CMP1001"
    last_id = docs[0]["complaint_id"]
    num = int(last_id[3:]) + 1
    return f"CMP{num}"


# ═══════════════════════════════════════════════════════════════════════════════
# STUDENT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_student(
    student_id: str,
    name: str,
    email: str,
    building: str,
) -> dict:
    """
    Insert a new student document.
    Returns the inserted document (serialized).
    Raises ValidationError or DuplicateKeyError on failure.
    """
    now = _now()
    doc = {
        "student_id": student_id.strip(),
        "name": name.strip(),
        "email": email.strip().lower(),
        "building": building.strip(),
        "created_at": now,
    }
    validate_student(doc)

    col = get_students_collection()
    try:
        result = col.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info("Student '%s' created (OID=%s).", student_id, result.inserted_id)
        return _serialize(doc)
    except DuplicateKeyError:
        raise DuplicateKeyError(
            f"Student ID '{student_id}' already exists.", None, None
        )
    except WriteError as exc:
        logger.error("MongoDB WriteError inserting student: %s", exc)
        raise


def get_student(student_id: str) -> Optional[dict]:
    """Return a single student document by student_id, or None."""
    doc = get_students_collection().find_one({"student_id": student_id})
    return _serialize(doc)


def get_students(
    search_text: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> list[dict]:
    """Return students, optionally filtered by a search string."""
    query: dict = {}
    if search_text:
        pattern = {"$regex": search_text, "$options": "i"}
        query["$or"] = [
            {"student_id": pattern},
            {"name": pattern},
            {"email": pattern},
            {"building": pattern},
        ]
    cursor = (
        get_students_collection()
        .find(query)
        .sort("student_id", ASCENDING)
        .skip(skip)
        .limit(limit)
    )
    return [_serialize(doc) for doc in cursor]


def count_students(search_text: Optional[str] = None) -> int:
    """Return the student count matching an optional search string."""
    query: dict = {}
    if search_text:
        pattern = {"$regex": search_text, "$options": "i"}
        query["$or"] = [
            {"student_id": pattern},
            {"name": pattern},
            {"email": pattern},
            {"building": pattern},
        ]
    return get_students_collection().count_documents(query)


def update_student(student_id: str, updates: dict[str, Any]) -> bool:
    """Update student fields. Returns True if modified."""
    if not updates:
        return False
    validate_student(updates, is_update=True)
    result = get_students_collection().update_one(
        {"student_id": student_id}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise KeyError(f"Student '{student_id}' not found.")
    return result.modified_count > 0


def delete_student(student_id: str) -> bool:
    """
    Delete a student only if they have no associated complaints.
    Raises ValueError if complaints exist.
    """
    complaint_count = get_complaints_collection().count_documents(
        {"student_id": student_id}
    )
    if complaint_count > 0:
        raise ValueError(
            f"Cannot delete student '{student_id}' — they have {complaint_count} "
            f"associated complaint(s). Resolve or reassign complaints first."
        )
    result = get_students_collection().delete_one({"student_id": student_id})
    if result.deleted_count:
        logger.warning("Student '%s' deleted.", student_id)
    return result.deleted_count > 0


def generate_student_id() -> str:
    """Generate the next student ID."""
    col = get_students_collection()
    docs = col.find(
        {"student_id": {"$regex": r"^STU\d+$"}},
        {"student_id": 1, "_id": 0},
    ).sort("student_id", DESCENDING).limit(1)
    docs = list(docs)
    if not docs:
        return "STU101"
    last_id = docs[0]["student_id"]
    num = int(last_id[3:]) + 1
    return f"STU{num}"


def get_all_student_ids() -> list[str]:
    """Return a sorted list of all student_id values."""
    return sorted(
        get_students_collection().distinct("student_id")
    )
