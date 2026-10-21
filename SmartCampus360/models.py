"""
models.py - MongoDB JSON Schema validators and index definitions.

All schema validation is applied to MongoDB via $jsonSchema.
Additional business-logic validation is enforced in validators.py (Python layer).
"""

from __future__ import annotations

import logging

import pymongo
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid, OperationFailure

import config
from database import get_database

logger = logging.getLogger(__name__)


# ─── $jsonSchema Definitions ──────────────────────────────────────────────────

COMPLAINT_JSON_SCHEMA: dict = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "complaint_id",
            "student_id",
            "category",
            "description",
            "location",
            "priority",
            "status",
            "department",
            "created_at",
            "updated_at",
        ],
        "properties": {
            "complaint_id": {
                "bsonType": "string",
                "description": "Unique complaint identifier, required.",
            },
            "student_id": {
                "bsonType": "string",
                "description": "Student ID who filed the complaint, required.",
            },
            "category": {
                "bsonType": "string",
                "enum": config.CATEGORIES,
                "description": f"Must be one of {config.CATEGORIES}.",
            },
            "description": {
                "bsonType": "string",
                "minLength": config.MIN_DESCRIPTION_LENGTH,
                "maxLength": config.MAX_DESCRIPTION_LENGTH,
                "description": (
                    f"Complaint description, min {config.MIN_DESCRIPTION_LENGTH} chars."
                ),
            },
            "location": {
                "bsonType": "string",
                "description": "Campus building or location.",
            },
            "priority": {
                "bsonType": "string",
                "enum": config.PRIORITIES,
                "description": f"Must be one of {config.PRIORITIES}.",
            },
            "status": {
                "bsonType": "string",
                "enum": config.STATUSES,
                "description": f"Must be one of {config.STATUSES}.",
            },
            "department": {
                "bsonType": "string",
                "description": "Responsible department.",
            },
            "created_at": {
                "bsonType": "date",
                "description": "BSON Date — document creation timestamp.",
            },
            "updated_at": {
                "bsonType": "date",
                "description": "BSON Date — last modification timestamp.",
            },
            "resolved_at": {
                "bsonType": ["date", "null"],
                "description": "BSON Date when resolved, null otherwise.",
            },
            "resolution_notes": {
                "bsonType": ["string", "null"],
                "description": "Optional resolution notes.",
            },
            "additional_details": {
                "bsonType": ["string", "null"],
                "description": "Optional additional context.",
            },
        },
    }
}

STUDENT_JSON_SCHEMA: dict = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["student_id", "name", "email", "building", "created_at"],
        "properties": {
            "student_id": {
                "bsonType": "string",
                "description": "Unique student identifier, required.",
            },
            "name": {
                "bsonType": "string",
                "description": "Student full name.",
            },
            "email": {
                "bsonType": "string",
                "description": "Student email address.",
            },
            "building": {
                "bsonType": "string",
                "description": "Hostel block or campus building.",
            },
            "created_at": {
                "bsonType": "date",
                "description": "BSON Date — record creation timestamp.",
            },
        },
        # Note: additionalProperties is intentionally omitted.
        # MongoDB adds '_id' automatically; including additionalProperties: false
        # would block that field.
    }
}


# ─── Database Initialisation ──────────────────────────────────────────────────

def initialize_database(force_validator_update: bool = False) -> dict[str, str]:
    """
    Idempotent database initialisation:
    - Creates collections with $jsonSchema validators if they don't exist.
    - Applies or updates validators on existing collections when
      force_validator_update=True.
    - Creates required indexes.

    Returns a dict of {collection_name: "created" | "existing" | "error"}.
    """
    db = get_database()
    results: dict[str, str] = {}

    existing_names = db.list_collection_names()

    for col_name, schema in [
        (config.COMPLAINTS_COLLECTION, COMPLAINT_JSON_SCHEMA),
        (config.STUDENTS_COLLECTION, STUDENT_JSON_SCHEMA),
    ]:
        if col_name not in existing_names:
            try:
                db.create_collection(
                    col_name,
                    validator=schema,
                    validationLevel="moderate",   # warn but don't block legacy docs
                    validationAction="error",      # reject invalid new/updated docs
                )
                logger.info("Created collection '%s' with validator.", col_name)
                results[col_name] = "created"
            except CollectionInvalid:
                # Race condition: another process created it first
                results[col_name] = "existing"
            except Exception as exc:
                logger.error("Failed to create '%s': %s", col_name, exc)
                results[col_name] = f"error: {exc}"
        else:
            results[col_name] = "existing"
            if force_validator_update:
                try:
                    db.command(
                        "collMod",
                        col_name,
                        validator=schema,
                        validationLevel="moderate",
                        validationAction="error",
                    )
                    logger.info("Updated validator for '%s'.", col_name)
                    results[col_name] = "validator_updated"
                except OperationFailure as exc:
                    logger.warning(
                        "Could not update validator for '%s': %s", col_name, exc
                    )

    _create_indexes(db)
    return results


def _create_indexes(db) -> None:
    """Create application indexes idempotently."""
    complaints = db[config.COMPLAINTS_COLLECTION]
    students = db[config.STUDENTS_COLLECTION]

    # complaints — unique complaint_id
    complaints.create_index(
        [("complaint_id", ASCENDING)], unique=True, name="idx_complaint_id_unique"
    )
    # complaints — frequent query fields
    complaints.create_index([("status", ASCENDING)], name="idx_status")
    complaints.create_index([("category", ASCENDING)], name="idx_category")
    complaints.create_index([("priority", ASCENDING)], name="idx_priority")
    complaints.create_index([("student_id", ASCENDING)], name="idx_student_id")
    complaints.create_index([("created_at", DESCENDING)], name="idx_created_at")
    complaints.create_index(
        [("status", ASCENDING), ("priority", ASCENDING)],
        name="idx_status_priority_compound",
    )

    # students — unique student_id
    students.create_index(
        [("student_id", ASCENDING)], unique=True, name="idx_student_id_unique"
    )
    students.create_index([("email", ASCENDING)], name="idx_email")

    logger.info("Indexes verified/created.")
